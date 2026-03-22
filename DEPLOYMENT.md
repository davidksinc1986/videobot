# Deploy paso a paso en Oracle Cloud (OCI) para VideoBot 24/7

Esta guía está escrita para principiantes.

## 1) Crear servidor en Oracle Cloud
1. Entra a Oracle Cloud Console.
2. Ve a **Compute > Instances > Create Instance**.
3. Nombre sugerido: `videobot-prod`.
4. Imagen: **Ubuntu 22.04**.
5. Shape: puedes usar Always Free (si te alcanza) o una VM pagada pequeña.
6. Crea/usa una llave SSH.
7. En red (VCN/Subnet), permite acceso público.

## 2) Abrir puertos en OCI
En **Networking > VCN > Security Lists** (o NSG), agrega reglas INGRESS:
- TCP 22 (SSH)
- TCP 80 (HTTP)
- TCP 443 (HTTPS)

> No expongas el puerto interno de la app (5000/5055) a internet.

## 3) Conectarte por SSH
Desde tu PC:
```bash
ssh ubuntu@IP_PUBLICA_DE_TU_VM
```
(Si tu usuario es `opc`, usa `opc@IP`.)

## 4) Instalar dependencias
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg nginx certbot python3-certbot-nginx git
```

## 5) Subir código y preparar entorno
```bash
cd /opt
sudo git clone <URL_DE_TU_REPO> videobot
sudo chown -R $USER:$USER /opt/videobot
cd /opt/videobot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
mkdir -p /opt/videobot-data
mkdir -p /opt/videobot-secrets
```

## 6) Variables de entorno (superuser y seguridad)
Crea archivo:
```bash
sudo nano /etc/videobot.env
```
Contenido recomendado:
```env
APP_PORT=5000
APP_SECRET_KEY=CAMBIA_ESTA_CLAVE_SUPER_LARGA_Y_ALEATORIA
SUPERUSER_EMAIL=admin@tudominio.com
SUPERUSER_PASSWORD=CAMBIA_ESTA_PASSWORD
VIDEOBOT_DATA_DIR=/opt/videobot-data
REDIS_URL=redis://localhost:6379/0
VIDEOBOT_RUN_EMBEDDED_SCHEDULER=false
```

> No guardes `.env`, `client_secret.json` ni `token.pickle` dentro del repo. Usa rutas fuera de `/opt/videobot`, por ejemplo `/opt/videobot-secrets/`.

Si usas OAuth de YouTube, guarda el secreto cliente fuera del repo:
```bash
sudo nano /opt/videobot-secrets/client_secret.json
```

## 7) Crear servicio web (systemd)
```bash
sudo nano /etc/systemd/system/videobot-web.service
```
Contenido:
```ini
[Unit]
Description=VideoBot Web
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/videobot
EnvironmentFile=/etc/videobot.env
ExecStart=/opt/videobot/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## 8) Crear servicio scheduler
```bash
sudo nano /etc/systemd/system/videobot-scheduler.service
```
Contenido:
```ini
[Unit]
Description=VideoBot Scheduler
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/videobot
EnvironmentFile=/etc/videobot.env
ExecStart=/opt/videobot/.venv/bin/python scheduler.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 9) Activar servicios
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now videobot-web
sudo systemctl enable --now videobot-scheduler
sudo systemctl status videobot-web
sudo systemctl status videobot-scheduler
```

## 10) Configurar Nginx con dominio
```bash
sudo nano /etc/nginx/sites-available/videobot
```
Contenido:
```nginx
server {
    server_name TU_DOMINIO.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Activar:
```bash
sudo ln -s /etc/nginx/sites-available/videobot /etc/nginx/sites-enabled/videobot
sudo nginx -t
sudo systemctl reload nginx
```

## 11) DNS del dominio
En tu proveedor DNS, crea registro A:
- `TU_DOMINIO.com` -> IP pública de tu VM Oracle.

Espera propagación (5-30 min normalmente).

## 12) SSL (https)
```bash
sudo certbot --nginx -d TU_DOMINIO.com
```

## 13) Acceso final
- URL: `https://TU_DOMINIO.com/login`
- Superuser:
  - user: el valor de `SUPERUSER_EMAIL`
  - pass: el valor de `SUPERUSER_PASSWORD`

## 14) Persistencia de datos (anti pérdida en git pull)
- `VIDEOBOT_DATA_DIR` guarda SQLite, videos, temp y usuarios fuera del repo.
- El backend migra automáticamente `usuarios/*.json` heredados a SQLite al iniciar.
- Puedes hacer `git pull` sin borrar progreso, métricas ni configuración.

## 15) Flujo multi-tenant recomendado
1. Entra como superuser.
2. Crea usuario tenant (email + password).
3. Deja defaults gratuitos (gTTS + Pixabay).
4. Si tenant no sube textos, sistema usa textos de nicho automáticamente.
5. Habilita/deshabilita redes por tenant desde superuser.
6. Tenant inicia sesión y solo puede editar su propio perfil/config.

## 16) Comandos útiles de soporte
```bash
journalctl -u videobot-web -f
journalctl -u videobot-scheduler -f
sudo systemctl restart videobot-web
sudo systemctl restart videobot-scheduler
```
