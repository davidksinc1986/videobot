# VideoBot SaaS Handoff (Multiusuario / Multitenant)

## Estado actual validado
- Ya existe autenticación **superuser** y **tenant user** con permisos separados.
- La plataforma usa aislamiento por usuario en JSON + sesiones por usuario.
- Se reforzó el modelo con:
  - `tenant_id` por cuenta.
  - `plan` por cuenta (`starter`, `growth`, `scale`) administrado por superuser.
  - Reglas de publicación por plan (gating de redes sociales).
  - `target_seconds` (20-45s) para adaptar guion/voz/video a duración objetivo.
  - `speech_history` para evitar repetición cuando se usa TXT de frases.

## Reglas de plan implementadas
- `starter`: YouTube.
- `growth`: YouTube + TikTok + Instagram.
- `scale`: YouTube + TikTok + Instagram + Facebook.

> El superuser define el plan y el sistema desactiva automáticamente plataformas no permitidas por ese plan.

## Flujo recomendado “llave en mano”
1. Superuser crea usuario con `tenant_id`, plan, nicho e idioma.
2. Usuario entra con su login propio y carga:
   - API keys (si tiene).
   - o sesión persistente (cookies/storage_state/token.pickle).
3. Superuser ajusta qué redes quedan habilitadas por plan.
4. Usuario define duración objetivo (20-45s), nicho y fuente de contenido (IA o TXT).
5. Generación y publicación automática respetando límites de plan y configuración.

## Guía rápida de proveedores (free vs paid)
- **Gratis / bajo costo**
  - gTTS: no requiere API key.
  - Pixabay: requiere cuenta y API key.
  - Pexels: requiere cuenta y API key.
- **Pago / freemium**
  - ElevenLabs: cuenta + API key + Voice ID.
  - OpenAI: API key con billing activo.

## Benchmarks (apps similares)
- OpusClip
- Vidyo.ai
- InVideo AI
- Kapwing (AI features)
- Canva Magic Studio (video workflows)
- Repurpose.io (distribución multi-red)

## Qué faltaría para nivel enterprise
1. Base de datos (PostgreSQL) con RBAC real y auditoría completa.
2. Cifrado de credenciales/API keys (KMS/Vault), no solo archivo JSON.
3. Cola de jobs (Celery/RQ) + workers escalables.
4. Facturación y suscripciones (Stripe) con enforcement server-side robusto.
5. Métricas y observabilidad (Sentry + Prometheus/Grafana).
6. Moderación/compliance por plataforma (copyright, políticas, riesgo de baneo).
7. AB testing de hooks, thumbnails y CTAs.
8. Biblioteca de plantillas por nicho con versionado.
9. Onboarding guiado dentro del panel para conectar cada red en < 5 minutos.
