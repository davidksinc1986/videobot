import os
import time
import random
import requests

# --- MoviePy Compatibilidad Robusta ---
try:
    from moviepy.editor import (
        VideoFileClip, AudioFileClip, CompositeVideoClip,
        ImageClip, ColorClip, AudioClip, concatenate_videoclips,
        concatenate_audioclips, vfx
    )
except ImportError:
    # Fallback para MoviePy 2.x+
    from moviepy.video.io.VideoFileClip import VideoFileClip
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
    from moviepy.video.VideoClip import ImageClip, ColorClip, AudioClip
    from moviepy.video.compositing.concatenate import concatenate_videoclips
    from moviepy.audio.compositing.concatenate import concatenate_audioclips
    import moviepy.video.fx.all as vfx

from gtts import gTTS
from voz_elevenlabs import generar_audio, QuotaExceededError
from config import VIDEOS_DIR, TEMP_DIR, DEFAULT_PEXELS_API_KEY, PIXABAY_API_KEY

# ============================
# CONFIGURACIÓN Y CONSTANTES
# ============================
TARGET_SECONDS_DEFAULT = 30
MIN_DURATION_SECONDS = 25
MAX_DURATION_SECONDS = 45
AUDIO_EPSILON = 0.1

NICHOS = {
    "motivacion": {
        "color": (255, 225, 0),
        "subcategorias": {
            "disciplina": {"temas_video": ["discipline", "hard work", "grind"], "estilo": "agresivo"},
            "mentalidad": {"temas_video": ["mindset", "growth", "focus"], "estilo": "reflexivo"},
            "exito": {"temas_video": ["success", "winning", "achievement"], "estilo": "aspiracional"}
        }
    },

    "dinero": {
        "color": (0, 255, 120),
        "subcategorias": {
            "riqueza": {"temas_video": ["luxury", "millionaire", "rich life"], "estilo": "aspiracional"},
            "inversion": {"temas_video": ["investment", "stocks", "portfolio"], "estilo": "educativo"},
            "negocios": {"temas_video": ["business", "startup", "entrepreneur"], "estilo": "estrategico"}
        }
    },

    "psicologia": {
        "color": (0, 255, 255),
        "subcategorias": {
            "conducta": {"temas_video": ["human behavior", "psychology facts"], "estilo": "analitico"},
            "emociones": {"temas_video": ["emotional intelligence", "confidence"], "estilo": "reflexivo"},
            "mente": {"temas_video": ["brain power", "subconscious"], "estilo": "profundo"}
        }
    },

    "viajes": {
        "color": (255, 220, 120),
        "subcategorias": {
            "aventura": {"temas_video": ["mountains", "exploration", "travel vlog"], "estilo": "emocional"},
            "lujo": {"temas_video": ["luxury resort", "5 star hotel"], "estilo": "aspiracional"},
            "naturaleza": {"temas_video": ["ocean", "forest", "paradise"], "estilo": "calmado"}
        }
    },

    "emprendimiento": {
        "color": (0, 200, 255),
        "subcategorias": {
            "startup": {"temas_video": ["startup office", "innovation"], "estilo": "estrategico"},
            "liderazgo": {"temas_video": ["leadership", "team building"], "estilo": "inspirador"},
            "productividad": {"temas_video": ["workflow", "deep work"], "estilo": "directo"}
        }
    },

    "finanzas_personales": {
        "color": (0, 180, 120),
        "subcategorias": {
            "ahorro": {"temas_video": ["saving money", "budget planning"], "estilo": "educativo"},
            "credito": {"temas_video": ["credit score", "debt"], "estilo": "alerta"},
            "inversion": {"temas_video": ["long term investing", "portfolio"], "estilo": "estrategico"}
        }
    },

    "trading": {
        "color": (0, 255, 80),
        "subcategorias": {
            "forex": {"temas_video": ["forex trading", "charts"], "estilo": "agresivo"},
            "crypto": {"temas_video": ["crypto chart", "market crash"], "estilo": "urgente"},
            "stocks": {"temas_video": ["wall street", "stock trader"], "estilo": "analitico"}
        }
    },

    "crypto": {
        "color": (255, 180, 0),
        "subcategorias": {
            "bitcoin": {"temas_video": ["bitcoin", "blockchain"], "estilo": "educativo"},
            "defi": {"temas_video": ["defi", "ethereum"], "estilo": "futurista"},
            "nfts": {"temas_video": ["nft", "digital art"], "estilo": "exploratorio"}
        }
    },

    "real_estate": {
        "color": (120, 200, 255),
        "subcategorias": {
            "lujo": {"temas_video": ["luxury mansion", "villa"], "estilo": "aspiracional"},
            "inversion": {"temas_video": ["property investment"], "estilo": "estrategico"},
            "tour": {"temas_video": ["house tour", "modern house"], "estilo": "visual"}
        }
    },

    "marketing_digital": {
        "color": (255, 0, 150),
        "subcategorias": {
            "ads": {"temas_video": ["facebook ads", "google ads"], "estilo": "directo"},
            "branding": {"temas_video": ["personal brand"], "estilo": "inspirador"},
            "contenido": {"temas_video": ["viral content", "content strategy"], "estilo": "educativo"}
        }
    },

    "inteligencia_artificial": {
        "color": (120, 120, 255),
        "subcategorias": {
            "automatizacion": {"temas_video": ["automation", "ai tools"], "estilo": "futurista"},
            "robotica": {"temas_video": ["robot", "machine learning"], "estilo": "exploratorio"},
            "productividad": {"temas_video": ["ai assistant", "workflow ai"], "estilo": "estrategico"}
        }
    },

    "programacion": {
        "color": (80, 180, 255),
        "subcategorias": {
            "web": {"temas_video": ["web development", "coding"], "estilo": "educativo"},
            "backend": {"temas_video": ["server", "api"], "estilo": "tecnico"},
            "apps": {"temas_video": ["mobile app", "software dev"], "estilo": "directo"}
        }
    },

    "saaS": {
        "color": (100, 255, 200),
        "subcategorias": {
            "automatizacion": {"temas_video": ["automation tools", "dashboard"], "estilo": "estrategico"},
            "crm": {"temas_video": ["crm software", "client management"], "estilo": "educativo"},
            "scaling": {"temas_video": ["scalable business", "growth tools"], "estilo": "directo"}
        }
    },

    "fitness": {
        "color": (255, 80, 80),
        "subcategorias": {
            "gym": {"temas_video": ["workout", "muscle training"], "estilo": "agresivo"},
            "salud": {"temas_video": ["healthy routine"], "estilo": "educativo"},
            "motivacion": {"temas_video": ["fitness motivation"], "estilo": "inspirador"}
        }
    },

    "salud": {
        "color": (80, 255, 80),
        "subcategorias": {
            "nutricion": {"temas_video": ["healthy food", "nutrition"], "estilo": "educativo"},
            "prevencion": {"temas_video": ["medical advice"], "estilo": "alerta"},
            "longevidad": {"temas_video": ["longevity", "wellness"], "estilo": "reflexivo"}
        }
    },

    "productividad": {
        "color": (255, 255, 120),
        "subcategorias": {
            "focus": {"temas_video": ["deep work", "focus routine"], "estilo": "directo"},
            "habitos": {"temas_video": ["morning routine", "discipline habits"], "estilo": "educativo"},
            "eficiencia": {"temas_video": ["time management", "workflow"], "estilo": "estrategico"}
        }
    },

    "habitos": {
        "color": (255, 200, 50),
        "subcategorias": {
            "disciplina": {"temas_video": ["daily discipline"], "estilo": "agresivo"},
            "mentalidad": {"temas_video": ["self improvement"], "estilo": "reflexivo"},
            "rutina": {"temas_video": ["morning habits"], "estilo": "educativo"}
        }
    },

    "biohacking": {
        "color": (0, 255, 200),
        "subcategorias": {
            "longevidad": {"temas_video": ["longevity", "cold exposure"], "estilo": "educativo"},
            "energia": {"temas_video": ["supplements", "brain boost"], "estilo": "analitico"},
            "salud": {"temas_video": ["biohacking routine"], "estilo": "futurista"}
        }
    },

    "relaciones": {
        "color": (255, 100, 150),
        "subcategorias": {
            "pareja": {"temas_video": ["relationship advice"], "estilo": "reflexivo"},
            "comunicacion": {"temas_video": ["communication skills"], "estilo": "educativo"},
            "atraccion": {"temas_video": ["dating tips"], "estilo": "directo"}
        }
    },

    "masculinidad": {
        "color": (200, 200, 255),
        "subcategorias": {
            "liderazgo": {"temas_video": ["alpha mindset"], "estilo": "agresivo"},
            "disciplina": {"temas_video": ["strong mindset"], "estilo": "directo"},
            "mentalidad": {"temas_video": ["confidence building"], "estilo": "inspirador"}
        }
    },

    "feminidad": {
        "color": (255, 150, 200),
        "subcategorias": {
            "empoderamiento": {"temas_video": ["women empowerment"], "estilo": "inspirador"},
            "confianza": {"temas_video": ["self confidence"], "estilo": "reflexivo"},
            "exito": {"temas_video": ["success woman"], "estilo": "aspiracional"}
        }
    },

    "educacion": {
        "color": (120, 255, 120),
        "subcategorias": {
            "estudio": {"temas_video": ["study tips"], "estilo": "educativo"},
            "online": {"temas_video": ["online learning"], "estilo": "directo"},
            "metodos": {"temas_video": ["learning techniques"], "estilo": "analitico"}
        }
    },

    "idiomas": {
        "color": (150, 255, 200),
        "subcategorias": {
            "ingles": {"temas_video": ["learn english"], "estilo": "educativo"},
            "fluidez": {"temas_video": ["speaking practice"], "estilo": "directo"},
            "gramatica": {"temas_video": ["grammar tips"], "estilo": "analitico"}
        }
    },

    "negocios_online": {
        "color": (0, 255, 150),
        "subcategorias": {
            "dropshipping": {"temas_video": ["dropshipping store"], "estilo": "estrategico"},
            "ecommerce": {"temas_video": ["online store"], "estilo": "educativo"},
            "automatizacion": {"temas_video": ["online automation"], "estilo": "futurista"}
        }
    },

    "amazon_fba": {
        "color": (255, 200, 0),
        "subcategorias": {
            "producto": {"temas_video": ["product research"], "estilo": "analitico"},
            "logistica": {"temas_video": ["amazon warehouse"], "estilo": "educativo"},
            "escalado": {"temas_video": ["scaling fba"], "estilo": "estrategico"}
        }
    },

    "afiliados": {
        "color": (0, 200, 100),
        "subcategorias": {
            "comisiones": {"temas_video": ["affiliate marketing"], "estilo": "educativo"},
            "embudos": {"temas_video": ["sales funnel"], "estilo": "estrategico"},
            "pasivo": {"temas_video": ["passive income"], "estilo": "aspiracional"}
        }
    },

    "ventas": {
        "color": (255, 100, 0),
        "subcategorias": {
            "cierre": {"temas_video": ["closing deal"], "estilo": "agresivo"},
            "negociacion": {"temas_video": ["negotiation tactics"], "estilo": "directo"},
            "psicologia": {"temas_video": ["sales psychology"], "estilo": "analitico"}
        }
    },

    "liderazgo": {
        "color": (150, 150, 255),
        "subcategorias": {
            "equipo": {"temas_video": ["team leadership"], "estilo": "inspirador"},
            "vision": {"temas_video": ["visionary leader"], "estilo": "aspiracional"},
            "empresa": {"temas_video": ["corporate leadership"], "estilo": "estrategico"}
        }
    },

    "coaching": {
        "color": (200, 255, 200),
        "subcategorias": {
            "vida": {"temas_video": ["life coaching"], "estilo": "reflexivo"},
            "negocios": {"temas_video": ["business coaching"], "estilo": "estrategico"},
            "mentalidad": {"temas_video": ["mind coaching"], "estilo": "inspirador"}
        }
    },

    "luxury": {
        "color": (255, 215, 0),
        "subcategorias": {
            "autos": {"temas_video": ["luxury car"], "estilo": "aspiracional"},
            "viajes": {"temas_video": ["private jet"], "estilo": "aspiracional"},
            "mansiones": {"temas_video": ["mansion tour"], "estilo": "visual"}
        }
    },

    "autos": {
        "color": (255, 50, 50),
        "subcategorias": {
            "supercar": {"temas_video": ["supercar"], "estilo": "aspiracional"},
            "review": {"temas_video": ["car review"], "estilo": "educativo"},
            "motor": {"temas_video": ["engine power"], "estilo": "analitico"}
        }
    },

    "tecnologia": {
        "color": (0, 150, 255),
        "subcategorias": {
            "gadgets": {"temas_video": ["smartphone"], "estilo": "educativo"},
            "futuro": {"temas_video": ["future tech"], "estilo": "futurista"},
            "review": {"temas_video": ["tech review"], "estilo": "analitico"}
        }
    },

    "gaming": {
        "color": (180, 0, 255),
        "subcategorias": {
            "esports": {"temas_video": ["esports"], "estilo": "emocional"},
            "setup": {"temas_video": ["gaming setup"], "estilo": "visual"},
            "highlights": {"temas_video": ["game highlights"], "estilo": "agresivo"}
        }
    },

    "noticias": {
        "color": (255, 0, 0),
        "subcategorias": {
            "economia": {"temas_video": ["economy news"], "estilo": "urgente"},
            "politica": {"temas_video": ["politics"], "estilo": "analitico"},
            "mundo": {"temas_video": ["world news"], "estilo": "directo"}
        }
    },

    "historia": {
        "color": (200, 150, 100),
        "subcategorias": {
            "antigua": {"temas_video": ["ancient history"], "estilo": "profundo"},
            "guerra": {"temas_video": ["war documentary"], "estilo": "dramatico"},
            "civilizacion": {"temas_video": ["civilization"], "estilo": "educativo"}
        }
    },

    "misterios": {
        "color": (80, 0, 120),
        "subcategorias": {
            "paranormal": {"temas_video": ["paranormal"], "estilo": "dramatico"},
            "conspiracion": {"temas_video": ["conspiracy"], "estilo": "urgente"},
            "oscuros": {"temas_video": ["dark history"], "estilo": "profundo"}
        }
    },

    "minimalismo": {
        "color": (220, 220, 220),
        "subcategorias": {
            "hogar": {"temas_video": ["declutter home"], "estilo": "calmado"},
            "vida": {"temas_video": ["simple living"], "estilo": "reflexivo"},
            "organizacion": {"temas_video": ["minimal lifestyle"], "estilo": "educativo"}
        }
    },

    "meditacion": {
        "color": (150, 255, 255),
        "subcategorias": {
            "mindfulness": {"temas_video": ["mindfulness"], "estilo": "calmado"},
            "respiracion": {"temas_video": ["breathing exercise"], "estilo": "calmado"},
            "zen": {"temas_video": ["zen meditation"], "estilo": "reflexivo"}
        }
    },

    "espiritualidad": {
        "color": (200, 180, 255),
        "subcategorias": {
            "energia": {"temas_video": ["energy flow"], "estilo": "profundo"},
            "manifestacion": {"temas_video": ["law of attraction"], "estilo": "inspirador"},
            "universo": {"temas_video": ["universe signs"], "estilo": "reflexivo"}
        }
    },

    "product_reviews": {
        "color": (255, 150, 50),
        "subcategorias": {
            "unboxing": {"temas_video": ["unboxing"], "estilo": "visual"},
            "comparacion": {"temas_video": ["comparison review"], "estilo": "analitico"},
            "top": {"temas_video": ["top products"], "estilo": "directo"}
        }
    }
}

# ============================
# HELPERS DE CONFIGURACIÓN
# ============================

def _pick_nicho(user):
    nicho = (user.get("nicho") or "motivacion").strip().lower()
    return nicho if nicho in NICHOS else "motivacion"

def _get_pexels_key(user):
    cred = user.get("credenciales", {}) or {}
    return (cred.get("pexels_api_key") or DEFAULT_PEXELS_API_KEY).strip()

def _gtts_lang(user_lang: str) -> str:
    lang = (user_lang or "es").strip().lower()
    return lang if lang in ("es", "en", "pt") else "es"

def _target_seconds(user: dict) -> int:
    try:
        v = int(user.get("target_seconds", TARGET_SECONDS_DEFAULT))
        return max(MIN_DURATION_SECONDS, min(v, MAX_DURATION_SECONDS))
    except:
        return TARGET_SECONDS_DEFAULT

def _humanize_key(key: str) -> str:
    # ✅ evita que el narrador lea "_" (underscore) y mejora lectura
    s = (key or "").strip().replace("_", " ")
    s = " ".join(s.split())
    return s

def _spoken_nicho(nicho_key: str) -> str:
    return _humanize_key(nicho_key).upper()

# ============================
# GENERACIÓN DE CONTENIDO
# ============================

def _build_script(user: dict, nicho_key: str, tema: str, seconds: int, estilo: str) -> str:
    """
    ✅ Genera guion con longitud aproximada a `seconds` (evita audios de 10s).
    ✅ Más variado: micro-historia + frases según estilo.
    ✅ No pronuncia underscores en nichos (NEGOCIOS ONLINE).
    """
    lang = _gtts_lang(user.get("idioma", "es"))
    hook = (user.get("hook_final") or "Suscríbete para más").strip()

    # objetivo de palabras aprox (ajusta si quieres)
    wps = 2.2  # palabras por segundo (aprox)
    target_words = max(45, int(seconds * wps))

    # ----- plantilla de micro-historias por idioma -----
    story_templates = {
        "es": [
            "Te cuento algo rápido: {a}. {b}. {c}. Y ahí entendí {d}.",
            "Un día {a}. Nadie lo vio, pero {b}. Después {c}. Eso cambió {d}.",
            "Esto pasó de verdad: {a}. Al principio dolió, pero {b}. Luego {c}. Moral: {d}.",
            "Si hoy estás perdido, escucha: {a}. Entonces {b}. Con el tiempo {c}. Resultado: {d}."
        ],
        "en": [
            "Quick story: {a}. {b}. {c}. That’s when I learned {d}.",
            "One day {a}. Nobody noticed, but {b}. Then {c}. Lesson: {d}.",
            "True story: {a}. It hurt at first, but {b}. Later {c}. Moral: {d}.",
            "If you feel stuck, listen: {a}. Then {b}. Over time {c}. Result: {d}."
        ],
        "pt": [
            "História rápida: {a}. {b}. {c}. Foi aí que eu entendi {d}.",
            "Um dia {a}. Ninguém viu, mas {b}. Depois {c}. Lição: {d}.",
            "História real: {a}. Doeu no começo, mas {b}. Depois {c}. Moral: {d}.",
            "Se você está travado, escuta: {a}. Então {b}. Com o tempo {c}. Resultado: {d}."
        ],
    }

    # ----- bancos por estilo -----
    # Nota: incluimos estilos que ya usas en NICHOS para que no caigan a "default"
    banks = {
        "agresivo": {
            "es": {
                "opener": f"Despierta. {tema} no es opcional.",
                "facts": [
                    "La disciplina lo decide todo.",
                    "Las excusas te roban años.",
                    "Si esperas motivación, perdiste.",
                    "Hazlo aunque no te apetezca.",
                    "Corta lo que te distrae.",
                    "Acción primero. Emoción después."
                ],
                "story_bits": [
                    "me levanté sin ganas",
                    "igual lo hice",
                    "nadie aplaudió, pero gané respeto propio",
                    "que la disciplina es amor propio"
                ]
            },
            "en": {
                "opener": f"Wake up. {tema} is not optional.",
                "facts": [
                    "Discipline decides everything.",
                    "Excuses steal years from you.",
                    "If you wait for motivation, you lose.",
                    "Do it even when you don’t feel like it.",
                    "Cut the distractions.",
                    "Action first. Feelings later."
                ],
                "story_bits": [
                    "I woke up with zero motivation",
                    "I did it anyway",
                    "nobody clapped, but I earned self-respect",
                    "discipline is self-love"
                ]
            },
            "pt": {
                "opener": f"Acorde. {tema} não é opcional.",
                "facts": [
                    "Disciplina decide tudo.",
                    "Desculpas roubam anos de você.",
                    "Se você espera motivação, você perde.",
                    "Faça mesmo sem vontade.",
                    "Corte distrações.",
                    "Ação primeiro. Emoção depois."
                ],
                "story_bits": [
                    "eu acordei sem vontade",
                    "eu fiz mesmo assim",
                    "ninguém aplaudiu, mas eu ganhei respeito próprio",
                    "disciplina é amor próprio"
                ]
            }
        },

        "educativo": {
            "es": {
                "opener": f"Entiende {tema}.",
                "facts": [
                    "Cuando dominas lo básico, lo avanzado se vuelve obvio.",
                    "Aprende una cosa y aplícala hoy.",
                    "Hazlo simple: idea, ejemplo, acción.",
                    "La claridad te da velocidad.",
                    "Sin práctica, no hay cambio.",
                    "Lo que se mide, mejora."
                ],
                "story_bits": [
                    "tomé una nota simple",
                    "la apliqué esa misma tarde",
                    "en una semana vi progreso real",
                    "que aprender sin aplicar es entretenimiento"
                ]
            },
            "en": {
                "opener": f"Understand {tema}.",
                "facts": [
                    "Master basics and advanced becomes obvious.",
                    "Learn one thing and apply it today.",
                    "Keep it simple: idea, example, action.",
                    "Clarity creates speed.",
                    "No practice, no change.",
                    "What gets measured improves."
                ],
                "story_bits": [
                    "I wrote one simple note",
                    "I applied it that same afternoon",
                    "within a week I saw real progress",
                    "learning without applying is entertainment"
                ]
            },
            "pt": {
                "opener": f"Entenda {tema}.",
                "facts": [
                    "Domine o básico e o avançado fica óbvio.",
                    "Aprenda uma coisa e aplique hoje.",
                    "Simples: ideia, exemplo, ação.",
                    "Clareza cria velocidade.",
                    "Sem prática, sem mudança.",
                    "O que é medido, melhora."
                ],
                "story_bits": [
                    "eu anotei algo simples",
                    "eu apliquei no mesmo dia",
                    "em uma semana vi progresso real",
                    "aprender sem aplicar é entretenimento"
                ]
            }
        },

        "aspiracional": {
            "es": {
                "opener": f"Esto es lo que {tema} puede desbloquear en tu vida.",
                "facts": [
                    "Más libertad. Más opciones. Más control.",
                    "La gente exitosa no tiene suerte: tiene sistemas.",
                    "La constancia convierte lo pequeño en grande.",
                    "No busques motivación: construye identidad.",
                    "90 días bien hechos cambian tu año.",
                    "Tu vida cambia cuando cambian tus decisiones."
                ],
                "story_bits": [
                    "decidí tomarme en serio",
                    "armé un sistema simple",
                    "me mantuve constante 30 días",
                    "que la libertad se construye"
                ]
            },
            "en": {
                "opener": f"This is what {tema} can unlock in your life.",
                "facts": [
                    "More freedom. More options. More control.",
                    "Successful people don’t have luck: they have systems.",
                    "Consistency turns small into big.",
                    "Don’t chase motivation: build identity.",
                    "90 strong days can change your year.",
                    "Your life changes when your decisions change."
                ],
                "story_bits": [
                    "I decided to take it seriously",
                    "I built a simple system",
                    "I stayed consistent for 30 days",
                    "freedom is built, not found"
                ]
            },
            "pt": {
                "opener": f"Isso é o que {tema} pode desbloquear na sua vida.",
                "facts": [
                    "Mais liberdade. Mais opções. Mais controle.",
                    "Pessoas de sucesso não têm sorte: têm sistemas.",
                    "Consistência transforma pequeno em grande.",
                    "Não corra atrás de motivação: construa identidade.",
                    "90 dias fortes mudam seu ano.",
                    "Sua vida muda quando suas decisões mudam."
                ],
                "story_bits": [
                    "eu decidi levar a sério",
                    "eu criei um sistema simples",
                    "eu fui constante por 30 dias",
                    "liberdade se constrói"
                ]
            }
        },

        "urgente": {
            "es": {
                "opener": f"Ahora mismo {tema} está cambiando las reglas.",
                "facts": [
                    "El mundo no espera.",
                    "Decide rápido y ejecuta más rápido.",
                    "Si lo postergas, alguien toma tu lugar.",
                    "Muévete antes de sentirte listo.",
                    "La acción te da claridad.",
                    "Hoy define tu semana."
                ],
                "story_bits": [
                    "vi una oportunidad",
                    "la tomé antes de estar listo",
                    "aprendí en el camino",
                    "que la velocidad gana"
                ]
            },
            "en": {
                "opener": f"Right now {tema} is changing the game.",
                "facts": [
                    "The world won’t wait.",
                    "Decide fast and execute faster.",
                    "If you delay, someone takes your spot.",
                    "Move before you feel ready.",
                    "Action creates clarity.",
                    "Today defines your week."
                ],
                "story_bits": [
                    "I saw an opportunity",
                    "I took it before I felt ready",
                    "I learned on the way",
                    "speed wins"
                ]
            },
            "pt": {
                "opener": f"Agora {tema} está mudando o jogo.",
                "facts": [
                    "O mundo não espera.",
                    "Decida rápido e execute mais rápido.",
                    "Se você adiar, alguém toma seu lugar.",
                    "Aja antes de se sentir pronto.",
                    "Ação cria clareza.",
                    "Hoje define sua semana."
                ],
                "story_bits": [
                    "eu vi uma oportunidade",
                    "eu fui antes de estar pronto",
                    "eu aprendi no caminho",
                    "velocidade vence"
                ]
            }
        },

        "analitico": {
            "es": {
                "opener": f"Analicemos {tema}.",
                "facts": [
                    "Todo tiene un patrón si miras suficiente tiempo.",
                    "Sin datos, es solo opinión.",
                    "Haz una hipótesis, prueba y ajusta.",
                    "Pequeñas mejoras se vuelven gigantes.",
                    "Mide lo importante y deja de adivinar.",
                    "Lo simple repetido gana."
                ],
                "story_bits": [
                    "anoté lo que funcionaba",
                    "eliminé lo que no",
                    "ajusté una variable por semana",
                    "que el progreso es medible"
                ]
            },
            "en": {
                "opener": f"Let’s analyze {tema}.",
                "facts": [
                    "Everything has a pattern if you look long enough.",
                    "Without data, it’s just opinion.",
                    "Hypothesis, test, adjust.",
                    "Small improvements compound fast.",
                    "Measure what matters and stop guessing.",
                    "Simple repeated wins."
                ],
                "story_bits": [
                    "I tracked what worked",
                    "I removed what didn’t",
                    "I adjusted one variable per week",
                    "progress is measurable"
                ]
            },
            "pt": {
                "opener": f"Vamos analisar {tema}.",
                "facts": [
                    "Tudo tem padrão se você olhar tempo suficiente.",
                    "Sem dados, é só opinião.",
                    "Hipótese, teste, ajuste.",
                    "Pequenas melhorias viram gigantes.",
                    "Meça o que importa e pare de adivinhar.",
                    "Simples repetido vence."
                ],
                "story_bits": [
                    "eu medi o que funcionava",
                    "eu cortei o que não",
                    "eu ajustei uma variável por semana",
                    "progresso é mensurável"
                ]
            }
        },

        "futurista": {
            "es": {
                "opener": f"El futuro pertenece a quienes dominan {tema}.",
                "facts": [
                    "Los que se adaptan ganan primero.",
                    "Aprende hoy lo que otros ignorarán.",
                    "Construye habilidades que el futuro pagará.",
                    "Piensa a largo plazo. Ejecuta hoy.",
                    "El futuro premia a los consistentes.",
                    "Domina lo básico y escala."
                ],
                "story_bits": [
                    "aprendí una habilidad nueva",
                    "al inicio fui lento",
                    "pero en semanas se volvió ventaja",
                    "que el futuro paga preparación"
                ]
            },
            "en": {
                "opener": f"The future belongs to those who master {tema}.",
                "facts": [
                    "Those who adapt win first.",
                    "Learn today what others ignore.",
                    "Build skills the future pays for.",
                    "Think long term. Execute today.",
                    "The future rewards consistency.",
                    "Master basics, then scale."
                ],
                "story_bits": [
                    "I learned a new skill",
                    "at first I was slow",
                    "weeks later it became an edge",
                    "the future pays preparation"
                ]
            },
            "pt": {
                "opener": f"O futuro pertence a quem domina {tema}.",
                "facts": [
                    "Quem se adapta vence primeiro.",
                    "Aprenda hoje o que outros ignoram.",
                    "Construa habilidades que o futuro paga.",
                    "Pense no longo prazo. Execute hoje.",
                    "O futuro premia consistência.",
                    "Domine o básico e escale."
                ],
                "story_bits": [
                    "eu aprendi uma habilidade nova",
                    "no começo fui lento",
                    "mas em semanas virou vantagem",
                    "o futuro paga preparação"
                ]
            }
        },

        # estilos "extra" que usas en NICHOS (para que no caigan a default)
        "reflexivo": {
            "es": {"opener": f"Respira. Hablemos de {tema}.", "facts": [
                "No todo es velocidad; también es dirección.",
                "A veces el cambio empieza con una sola decisión.",
                "Tu mente interpreta la vida antes de vivirla.",
                "Cuida lo que piensas cuando estás solo.",
                "La paz también es progreso.",
                "No te compares: compite contigo."
            ], "story_bits": ["me senté en silencio", "ordené mis ideas", "dejé ir una distracción", "que la claridad es poder"]},
            "en": {"opener": f"Take a breath. Let’s talk about {tema}.", "facts": [
                "It’s not only speed; it’s direction.",
                "Change starts with one decision.",
                "Your mind interprets life before you live it.",
                "Watch your thoughts when you’re alone.",
                "Peace is also progress.",
                "Don’t compare. Compete with yourself."
            ], "story_bits": ["I sat in silence", "I organized my thoughts", "I dropped one distraction", "clarity is power"]},
            "pt": {"opener": f"Respire. Vamos falar de {tema}.", "facts": [
                "Não é só velocidade; é direção.",
                "Mudança começa com uma decisão.",
                "Sua mente interpreta antes de viver.",
                "Cuide dos pensamentos quando está sozinho.",
                "Paz também é progresso.",
                "Não compare. Compita consigo."
            ], "story_bits": ["eu fiquei em silêncio", "organizei minhas ideias", "cortei uma distração", "clareza é poder"]},
        },

        "estrategico": {
            "es": {"opener": f"Estrategia rápida sobre {tema}.", "facts": [
                "Un sistema vence a la motivación.",
                "Define una meta y una métrica.",
                "Reduce fricción: hazlo fácil de ejecutar.",
                "Itera semanalmente, no cuando te acuerdas.",
                "Protege tu tiempo como un activo.",
                "Escala lo que funciona, corta lo que no."
            ], "story_bits": ["dibujé un plan simple", "lo convertí en rutina", "medí resultados", "que el plan gana al caos"]},
            "en": {"opener": f"Quick strategy on {tema}.", "facts": [
                "A system beats motivation.",
                "Define a goal and a metric.",
                "Reduce friction: make it easy to execute.",
                "Iterate weekly, not randomly.",
                "Protect time like an asset.",
                "Scale what works, cut what doesn’t."
            ], "story_bits": ["I wrote a simple plan", "turned it into a routine", "measured results", "plans beat chaos"]},
            "pt": {"opener": f"Estratégia rápida sobre {tema}.", "facts": [
                "Um sistema vence motivação.",
                "Defina meta e métrica.",
                "Reduza fricção: fácil de executar.",
                "Itere semanalmente.",
                "Proteja seu tempo como ativo.",
                "Escale o que funciona, corte o resto."
            ], "story_bits": ["fiz um plano simples", "virei rotina", "medi resultados", "plano vence caos"]},
        },

        "profundo": {
            "es": {"opener": f"Esto va profundo: {tema}.", "facts": [
                "A veces lo que temes es tu siguiente nivel.",
                "El ego quiere atajos; el alma quiere verdad.",
                "Lo que niegas te controla.",
                "La disciplina también es espiritual.",
                "Tu identidad decide tu destino.",
                "No huyas: observa."
            ], "story_bits": ["miré mi miedo", "no corrí", "lo enfrenté despacio", "que el miedo era una puerta"]},
            "en": {"opener": f"Let’s go deep: {tema}.", "facts": [
                "Sometimes what you fear is your next level.",
                "Ego wants shortcuts; soul wants truth.",
                "What you deny controls you.",
                "Discipline is spiritual too.",
                "Identity decides destiny.",
                "Don’t run. Observe."
            ], "story_bits": ["I faced my fear", "I didn’t run", "I moved slowly through it", "fear was a doorway"]},
            "pt": {"opener": f"Vamos fundo: {tema}.", "facts": [
                "Às vezes o que você teme é seu próximo nível.",
                "Ego quer atalho; alma quer verdade.",
                "O que você nega te controla.",
                "Disciplina também é espiritual.",
                "Identidade decide destino.",
                "Não fuja: observe."
            ], "story_bits": ["encarei meu medo", "não fugi", "passei por ele devagar", "medo era uma porta"]},
        },

        "emocional": {
            "es": {"opener": f"Esto te va a tocar: {tema}.", "facts": [
                "No estás tarde: estás a una decisión.",
                "Lo que sientes importa, pero no te gobierna.",
                "A veces llorar es resetear.",
                "La valentía también tiembla.",
                "Sigue aunque sea lento.",
                "Un día vas a agradecer no rendirte."
            ], "story_bits": ["me sentí roto", "pero seguí", "paso a paso", "que la esperanza se entrena"]},
            "en": {"opener": f"This will hit you: {tema}.", "facts": [
                "You’re not late; you’re one decision away.",
                "Feelings matter, but they don’t lead.",
                "Sometimes crying is a reset.",
                "Courage shakes too.",
                "Keep going even if slow.",
                "One day you’ll thank yourself."
            ], "story_bits": ["I felt broken", "but I kept going", "step by step", "hope is trained"]},
            "pt": {"opener": f"Isso vai te tocar: {tema}.", "facts": [
                "Você não está atrasado; está a uma decisão.",
                "Sentimentos importam, mas não mandam.",
                "Chorar às vezes é reset.",
                "Coragem também treme.",
                "Siga mesmo devagar.",
                "Um dia você vai agradecer."
            ], "story_bits": ["eu me senti quebrado", "mas continuei", "passo a passo", "esperança se treina"]},
        },

        "calmado": {
            "es": {"opener": f"Tranquilo. {tema}.", "facts": [
                "Respira profundo y regresa al presente.",
                "Lo simple repetido trae paz.",
                "No todo se resuelve hoy, pero hoy se empieza.",
                "Haz una cosa bien, ahora.",
                "Menos ruido, más intención.",
                "Tu mente necesita descanso para crear."
            ], "story_bits": ["apagó el ruido", "volví a lo básico", "me enfoqué en una cosa", "que la calma también produce"]},
            "en": {"opener": f"Slow down. {tema}.", "facts": [
                "Breathe and come back to the present.",
                "Simple repeated creates peace.",
                "Not everything is solved today, but today you start.",
                "Do one thing well, now.",
                "Less noise, more intention.",
                "Your mind needs rest to create."
            ], "story_bits": ["I turned down the noise", "went back to basics", "focused on one thing", "calm can produce too"]},
            "pt": {"opener": f"Calma. {tema}.", "facts": [
                "Respire e volte ao presente.",
                "Simples repetido traz paz.",
                "Nem tudo se resolve hoje, mas hoje começa.",
                "Faça uma coisa bem, agora.",
                "Menos ruído, mais intenção.",
                "A mente precisa descanso para criar."
            ], "story_bits": ["eu baixei o ruído", "voltei ao básico", "fiz uma coisa só", "calma também produz"]},
        },

        "directo": {
            "es": {"opener": f"Directo al grano sobre {tema}.", "facts": [
                "Haz esto: uno, decide. Dos, ejecuta. Tres, repite.",
                "Elimina una distracción hoy.",
                "Bloquea 30 minutos y hazlo.",
                "No negocies contigo.",
                "Termina lo que empiezas.",
                "Listo. Sin drama."
            ], "story_bits": ["cerré redes", "abrí el trabajo", "terminé en 30 minutos", "que lo simple funciona"]},
            "en": {"opener": f"Straight to the point on {tema}.", "facts": [
                "Do this: decide, execute, repeat.",
                "Remove one distraction today.",
                "Block 30 minutes and do it.",
                "Don’t negotiate with yourself.",
                "Finish what you start.",
                "Done. No drama."
            ], "story_bits": ["I closed socials", "opened the work", "finished in 30 minutes", "simple works"]},
            "pt": {"opener": f"Direto ao ponto sobre {tema}.", "facts": [
                "Faça: decide, executa, repete.",
                "Corte uma distração hoje.",
                "Bloqueie 30 minutos e faça.",
                "Não negocie consigo.",
                "Termine o que começa.",
                "Pronto."
            ], "story_bits": ["eu fechei redes", "abri o trabalho", "terminei em 30 minutos", "simples funciona"]},
        },

        "tecnico": {
            "es": {"opener": f"Tip técnico sobre {tema}.", "facts": [
                "Divide el problema en pasos pequeños.",
                "Primero haz que funcione, luego optimiza.",
                "Una variable a la vez.",
                "Registra errores y aprende del patrón.",
                "Automatiza lo repetitivo.",
                "Documenta lo que arreglas."
            ], "story_bits": ["identifiqué el bug", "lo aislé", "probé una cosa", "que el método vence al caos"]},
            "en": {"opener": f"Technical tip on {tema}.", "facts": [
                "Break it into small steps.",
                "Make it work first, then optimize.",
                "One variable at a time.",
                "Log errors and learn patterns.",
                "Automate the repetitive.",
                "Document fixes."
            ], "story_bits": ["I found the bug", "isolated it", "tested one thing", "method beats chaos"]},
            "pt": {"opener": f"Dica técnica sobre {tema}.", "facts": [
                "Quebre em passos pequenos.",
                "Faça funcionar, depois otimize.",
                "Uma variável por vez.",
                "Registre erros e padrões.",
                "Automatize o repetitivo.",
                "Documente correções."
            ], "story_bits": ["eu achei o bug", "isolei", "testei uma coisa", "método vence caos"]},
        },

        "alerta": {
            "es": {"opener": f"Alerta sobre {tema}.", "facts": [
                "Cuidado: esto es donde la gente se destruye sin darse cuenta.",
                "Si no lo controlas, te controla.",
                "Revisa tus hábitos financieros hoy.",
                "Evita decisiones por impulso.",
                "Protege tu futuro con una regla simple.",
                "Un error repetido se vuelve deuda."
            ], "story_bits": ["ignoré una señal", "pagué el precio", "aprendí la lección", "que prevenir es ganar"]},
            "en": {"opener": f"Warning about {tema}.", "facts": [
                "Careful: this is where people self-destruct slowly.",
                "If you don’t control it, it controls you.",
                "Review your habits today.",
                "Avoid impulse decisions.",
                "Protect your future with a simple rule.",
                "A repeated mistake becomes debt."
            ], "story_bits": ["I ignored a signal", "paid the price", "learned the lesson", "prevention wins"]},
            "pt": {"opener": f"Alerta sobre {tema}.", "facts": [
                "Cuidado: aqui as pessoas se destroem devagar.",
                "Se você não controla, te controla.",
                "Revise seus hábitos hoje.",
                "Evite impulso.",
                "Proteja seu futuro com uma regra simples.",
                "Erro repetido vira dívida."
            ], "story_bits": ["eu ignorei um sinal", "paguei o preço", "aprendi a lição", "prevenir é vencer"]},
        },

        "inspirador": {
            "es": {"opener": f"Escucha esto sobre {tema}.", "facts": [
                "Tú puedes cambiar tu historia.",
                "Nadie viene a salvarte, pero tú puedes salvarte.",
                "Hazlo por tu yo del futuro.",
                "La constancia te convierte en alguien nuevo.",
                "Cada día cuenta.",
                "No te detengas."
            ], "story_bits": ["estaba a punto de rendirme", "seguí un día más", "luego otro", "que la fuerza se construye"]},
            "en": {"opener": f"Listen to this about {tema}.", "facts": [
                "You can change your story.",
                "No one is coming, but you can save yourself.",
                "Do it for your future self.",
                "Consistency turns you into someone new.",
                "Every day counts.",
                "Don’t stop."
            ], "story_bits": ["I was about to quit", "I kept going one more day", "then another", "strength is built"]},
            "pt": {"opener": f"Escuta isso sobre {tema}.", "facts": [
                "Você pode mudar sua história.",
                "Ninguém vem te salvar, mas você pode.",
                "Faça pelo seu eu do futuro.",
                "Consistência te transforma.",
                "Cada dia conta.",
                "Não pare."
            ], "story_bits": ["eu quase desisti", "continuei mais um dia", "depois outro", "força se constrói"]},
        },

        "visual": {
            "es": {"opener": f"Mira esto sobre {tema}.", "facts": [
                "Observa los detalles.",
                "La calidad se nota en lo pequeño.",
                "Lo simple bien hecho se ve caro.",
                "Enfócate en luz, forma y ritmo.",
                "Menos, pero mejor.",
                "Listo: estética limpia."
            ], "story_bits": ["me fijé en un detalle", "lo ajusté", "todo se vio mejor", "que el ojo se entrena"]},
            "en": {"opener": f"Watch this about {tema}.", "facts": [
                "Notice the details.",
                "Quality shows in small things.",
                "Simple done well looks expensive.",
                "Focus on light, shape, rhythm.",
                "Less, but better.",
                "Clean aesthetics."
            ], "story_bits": ["I noticed one detail", "tweaked it", "everything looked better", "your eye can be trained"]},
            "pt": {"opener": f"Olha isso sobre {tema}.", "facts": [
                "Repare nos detalhes.",
                "Qualidade aparece no pequeno.",
                "Simples bem feito parece caro.",
                "Foco em luz, forma, ritmo.",
                "Menos, porém melhor.",
                "Estética limpa."
            ], "story_bits": ["eu notei um detalhe", "ajustei", "tudo melhorou", "o olhar se treina"]},
        },

        "exploratorio": {
            "es": {"opener": f"Exploremos {tema}.", "facts": [
                "Hay más de una forma de hacerlo bien.",
                "Prueba, aprende y ajusta.",
                "La curiosidad abre puertas.",
                "Lo nuevo siempre se siente raro al inicio.",
                "Si te interesa, profundiza.",
                "Experimenta sin miedo."
            ], "story_bits": ["probé algo nuevo", "fallé rápido", "aprendí rápido", "que explorar acelera"]},
            "en": {"opener": f"Let’s explore {tema}.", "facts": [
                "There’s more than one right way.",
                "Try, learn, adjust.",
                "Curiosity opens doors.",
                "New always feels weird at first.",
                "If it interests you, go deeper.",
                "Experiment without fear."
            ], "story_bits": ["I tried something new", "failed fast", "learned fast", "exploration accelerates"]},
            "pt": {"opener": f"Vamos explorar {tema}.", "facts": [
                "Há mais de um jeito certo.",
                "Teste, aprenda, ajuste.",
                "Curiosidade abre portas.",
                "Novo parece estranho no início.",
                "Se te interessa, aprofunde.",
                "Experimente sem medo."
            ], "story_bits": ["eu tentei algo novo", "errei rápido", "aprendi rápido", "explorar acelera"]},
        },

        "dramatico": {
            "es": {"opener": f"Esto se pone serio: {tema}.", "facts": [
                "Hay decisiones que te marcan.",
                "Un pequeño error puede costar caro.",
                "No ignores las señales.",
                "Lo que haces en silencio define tu final.",
                "Cambia antes de que sea tarde.",
                "Hoy es el punto de giro."
            ], "story_bits": ["ignoré una advertencia", "perdí tiempo", "aprendí a la fuerza", "que el precio sube con el tiempo"]},
            "en": {"opener": f"This gets serious: {tema}.", "facts": [
                "Some decisions leave a mark.",
                "Small mistakes can be expensive.",
                "Don’t ignore signals.",
                "What you do in silence defines the ending.",
                "Change before it’s too late.",
                "Today is the turning point."
            ], "story_bits": ["I ignored a warning", "lost time", "learned the hard way", "the price rises over time"]},
            "pt": {"opener": f"Isso fica sério: {tema}.", "facts": [
                "Algumas decisões marcam.",
                "Erros pequenos custam caro.",
                "Não ignore sinais.",
                "O que você faz em silêncio define o final.",
                "Mude antes que seja tarde.",
                "Hoje é o ponto de virada."
            ], "story_bits": ["eu ignorei um aviso", "perdi tempo", "aprendi na dor", "o preço sobe com o tempo"]},
        },
    }

    style_pack = banks.get(estilo) or banks.get("educativo")
    pack = style_pack.get(lang) or style_pack.get("es")

    opener = pack.get("opener") or f"Enfócate en {tema}."
    facts = (pack.get("facts") or []).copy()
    story_bits = (pack.get("story_bits") or []).copy()

    # barajamos para variar
    random.shuffle(facts)
    random.shuffle(story_bits)

    # construimos una micro-historia corta (A,B,C,D)
    tpl = random.choice(story_templates.get(lang, story_templates["es"]))
    # por si no hay suficientes bits, repetimos
    while len(story_bits) < 4:
        story_bits += story_bits[:]
        if not story_bits:
            story_bits = ["hice un cambio", "seguí", "mejoré", "que todo se construye"]
            break

    story = tpl.format(a=story_bits[0], b=story_bits[1], c=story_bits[2], d=story_bits[3])

    # partes iniciales
    parts = []
    parts.append(opener)
    parts.append(story)

    # relleno hasta target_words
    i = 0
    while len(" ".join(parts).split()) < target_words:
        if i >= len(facts):
            random.shuffle(facts)
            i = 0
        if facts:
            parts.append(facts[i])
            i += 1
        else:
            parts.append(opener)

    # cierre
    spoken = _spoken_nicho(nicho_key)
    text = f"{spoken}. " + " ".join(parts).strip()
    if hook:
        text = f"{text} {hook}"

    return text


def _download_pexels_video(query, api_key, out_path):
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=15&orientation=portrait"
    headers = {"Authorization": api_key}

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        videos = data.get("videos", [])

        if not videos:
            return False

        chosen = random.choice(videos)
        files = [f for f in chosen.get("video_files", []) if f.get("width")]
        files_sorted = sorted(files, key=lambda x: x["width"], reverse=True)

        file_url = files_sorted[0].get("link")
        if not file_url:
            return False

        vr = requests.get(file_url, timeout=90)
        vr.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(vr.content)

        return os.path.exists(out_path) and os.path.getsize(out_path) > 1000

    except Exception as e:
        print(f"❌ Error Pexels: {e}")
        return False


def _download_pixabay_video(query, out_path, api_key=None):
    """
    Pixabay videos NO soporta orientation=vertical.
    Elegimos el mejor candidato:
      1) vertical (height > width)
      2) más cercano a ratio 9:16 (w/h ~= 0.5625)
    """
    url = "https://pixabay.com/api/videos/"
    params = {
        "key": (api_key or PIXABAY_API_KEY),
        "q": query,
        "safesearch": "true",
        "per_page": 50,
        "order": "popular",
    }

    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        hits = data.get("hits", [])
        if not hits:
            return False

        target_ratio = 9 / 16  # 0.5625 (w/h)
        candidates = []

        for h in hits:
            vids = (h.get("videos") or {})
            for key in ("large", "medium", "small", "tiny"):
                v = vids.get(key)
                if not v:
                    continue

                w = int(v.get("width") or 0)
                hh = int(v.get("height") or 0)
                vurl = v.get("url")
                size = int(v.get("size") or 0)

                if not vurl or w <= 0 or hh <= 0:
                    continue

                ratio = w / hh
                ratio_diff = abs(ratio - target_ratio)
                is_vertical = hh > w

                score = (0 if is_vertical else 10) + ratio_diff
                candidates.append((score, ratio_diff, is_vertical, size, vurl, w, hh))

        if not candidates:
            return False

        candidates.sort(key=lambda x: (x[0], -x[3]))
        best = candidates[0]
        best_url = best[4]
        print(f"📥 Pixabay elegido: {best_url} ({best[5]}x{best[6]}) vertical={best[2]} diff={best[1]:.3f}")

        vr = requests.get(best_url, timeout=120)
        vr.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(vr.content)

        return os.path.exists(out_path) and os.path.getsize(out_path) > 1000

    except Exception as e:
        print(f"❌ Error Pixabay: {e}")
        return False



def _get_pixabay_key(user):
    cred = user.get("credenciales", {}) or {}
    return (cred.get("pixabay_api_key") or PIXABAY_API_KEY).strip()


def _read_lines_file(path: str) -> list[str]:
    if not path:
        return []
    if not os.path.exists(path) or not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f.readlines() if ln.strip() and not ln.strip().startswith("#")]
    except Exception:
        return []


def _script_from_nicho_library(user: dict, nicho_key: str, seconds: int) -> str:
    lines = _read_lines_file(os.path.join("nichos", f"{nicho_key}.txt"))
    if not lines:
        return ""

    hook = (user.get("hook_final") or "Suscríbete para más").strip()
    # evitamos frases sueltas random: armamos intro + desarrollo + cierre
    take = min(4, max(2, int(seconds / 12)))
    picked = random.sample(lines, k=take) if len(lines) >= take else lines

    intro = f"En {nicho_key.replace('_', ' ')} recuerda esto:"
    body = " ".join(picked[:3])
    closing = picked[-1] if len(picked) > 1 else "Aplica esto hoy mismo."
    return f"{intro} {body} {closing} {hook}".strip()


def _resolve_script_text(user: dict, nicho_key: str, tema: str, seconds: int, estilo: str) -> str:
    source = (user.get("content_source") or "ai").strip().lower()
    requested_file = (user.get("content_file_path") or "").strip()

    if source == "file":
        if requested_file:
            lines = _read_lines_file(requested_file)
            if lines:
                hook = (user.get("hook_final") or "Suscríbete para más").strip()
                take = min(4, max(2, int(seconds / 12)))
                picked = random.sample(lines, k=take) if len(lines) >= take else lines
                return (" ".join(picked) + f" {hook}").strip()

        # si no proporciona textos o el archivo viene vacío, caer a nicho por defecto
        fallback_nicho_text = _script_from_nicho_library(user, nicho_key, seconds)
        if fallback_nicho_text:
            return fallback_nicho_text

        print("⚠️ content_source=file sin textos válidos; usando generador IA local")

    provider = (user.get("script_provider") or "local").strip().lower()
    if provider == "openai":
        cred = user.get("credenciales", {}) or {}
        api_key = (cred.get("openai_api_key") or "").strip()
        if api_key:
            try:
                prompt = f"Crea un guion corto de {seconds} segundos en idioma {user.get('idioma','es')} sobre {tema} con estilo {estilo}."
                r = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": "Eres un guionista para shorts verticales de marketing. Escribe en tono humano y coherente."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.8,
                    },
                    timeout=40,
                )
                r.raise_for_status()
                data = r.json()
                text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
                if text:
                    return text
            except Exception as e:
                print(f"⚠️ OpenAI script provider falló: {e}")

    # fallback coherente por nicho antes del generador aleatorio
    niche_text = _script_from_nicho_library(user, nicho_key, seconds)
    if niche_text:
        return niche_text

    return _build_script(user, nicho_key, tema, seconds, estilo)


def _provider_order(user: dict, kind: str) -> list[str]:
    setting_key = "voice_provider" if kind == "voice" else "video_provider"
    selected = (user.get(setting_key) or "auto").strip().lower()
    if kind == "voice":
        default = ["elevenlabs", "gtts"]
    else:
        default = ["pexels", "pixabay", "fallback"]

    if selected == "auto":
        return default
    if selected in default:
        return [selected] + [x for x in default if x != selected]
    return default


def _generate_tts(user: dict, texto: str, out_mp3: str) -> None:
    cred = user.get("credenciales", {}) or {}
    providers = _provider_order(user, "voice")

    for provider in providers:
        try:
            if provider == "elevenlabs":
                eleven_key = (cred.get("elevenlabs_api_key") or "").strip()
                eleven_voice = (cred.get("eleven_voice_id") or "").strip()
                if eleven_key and eleven_voice:
                    generar_audio(texto, out_mp3, api_key=eleven_key, voice_id=eleven_voice)
                    return
            elif provider == "gtts":
                tts = gTTS(text=texto, lang=_gtts_lang(user.get("idioma", "es")))
                tts.save(out_mp3)
                return
        except QuotaExceededError:
            print("⚠️ ElevenLabs quota exceeded, probando siguiente proveedor...")
        except Exception as e:
            print(f"⚠️ Voz provider {provider} falló: {e}")

    tts = gTTS(text=texto, lang=_gtts_lang(user.get("idioma", "es")))
    tts.save(out_mp3)


# ============================
# 9:16 FORZADO (crop centrado)
# ============================

def _force_vertical_9_16(clip):
    """
    Fuerza 9:16 (vertical) SIN deformar.
    Hace crop centrado (corta lados o corta arriba/abajo si hace falta).
    """
    target_ratio = 9 / 16  # w/h

    w, h = clip.size
    if not w or not h:
        return clip

    current_ratio = w / h

    if current_ratio > target_ratio:
        new_w = int(h * target_ratio)
        x1 = max(0, (w - new_w) // 2)
        x2 = x1 + new_w
        return clip.crop(x1=x1, y1=0, x2=x2, y2=h)

    if current_ratio < target_ratio:
        new_h = int(w / target_ratio)
        y1 = max(0, (h - new_h) // 2)
        y2 = y1 + new_h
        return clip.crop(x1=0, y1=y1, x2=w, y2=y2)

    return clip



def _avatar_overlay_clip(user: dict, duration: float):
    mode = (user.get("avatar_mode") or "none").strip().lower()
    path = (user.get("avatar_image_path") or "").strip()
    if mode not in ("photo", "ai_sketch"):
        return None
    if not path or not os.path.exists(path):
        return None
    try:
        clip = ImageClip(path).set_duration(duration)
        clip = clip.resize(height=740).set_position(("center", "center"))
        opacity = 0.80 if mode == "photo" else 0.45
        return clip.set_opacity(opacity)
    except Exception as e:
        print(f"⚠️ No se pudo aplicar avatar overlay: {e}")
        return None


# ============================
# PROCESAMIENTO DE VIDEO
# ============================

def generar_video_usuario(user: dict) -> str:
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    nicho_key = _pick_nicho(user)
    subcats = NICHOS[nicho_key]["subcategorias"]

    target_dur = _target_seconds(user)

    ts = int(time.time())
    base_name = f"{user.get('nombre', 'user')}_{ts}"
    temp_video = os.path.join(TEMP_DIR, f"{base_name}_raw.mp4")
    temp_audio = os.path.join(TEMP_DIR, f"{base_name}.mp3")
    out_video = os.path.join(VIDEOS_DIR, f"{base_name}.mp4")

    # 1) Limpieza antes de iniciar (blindaje)
    for p in (temp_video, temp_audio):
        try:
            if os.path.exists(p):
                os.remove(p)
        except:
            pass

    # 2) Descargar video robusto
    max_intentos = 5
    descargado = False
    tema = None
    estilo = "educativo"  # default seguro

    for _ in range(max_intentos):
        subcat_key = random.choice(list(subcats.keys()))
        subcat = subcats[subcat_key]

        tema = random.choice(subcat["temas_video"])
        estilo = subcat.get("estilo", "educativo") or "educativo"

        print(f"🔎 Intentando descargar video para tema: {tema}")

        sources = _provider_order(user, "video")

        ok = False
        for source in sources:
            try:
                if os.path.exists(temp_video):
                    os.remove(temp_video)
            except:
                pass

            if source == "pexels":
                print("🎬 Intentando desde Pexels...")
                ok = _download_pexels_video(tema, _get_pexels_key(user), temp_video)
            elif source == "pixabay":
                print("🎬 Intentando desde Pixabay...")
                ok = _download_pixabay_video(tema, temp_video, _get_pixabay_key(user))
            elif source == "fallback":
                ok = False

            if ok and os.path.exists(temp_video) and os.path.getsize(temp_video) > 1000:
                descargado = True
                break

        if descargado:
            break

    # 3) Fallback sólido
    if not descargado:
        print("⚠️ Pexels/Pixabay fallaron. Generando video fallback sólido.")
        color = NICHOS[nicho_key]["color"]
        fallback_clip = ColorClip(size=(1080, 1920), color=color, duration=target_dur)
        fallback_clip.write_videofile(temp_video, fps=30, codec="libx264", audio=False, logger=None)
        fallback_clip.close()

    # 4) Audio (ahora largo y variado)
    texto = _resolve_script_text(user, nicho_key, tema or nicho_key, target_dur, estilo)
    _generate_tts(user, texto, temp_audio)

    if not os.path.exists(temp_audio) or os.path.getsize(temp_audio) < 200:
        raise Exception("No se pudo generar el audio TTS")

    # 5) Render final con 9:16 forzado y sync
    if not os.path.exists(temp_video) or os.path.getsize(temp_video) < 1000:
        raise Exception("Video base no existe o está vacío después del fallback/descarga")

    try:
        with VideoFileClip(temp_video) as clip, AudioFileClip(temp_audio) as audio:
            clip = _force_vertical_9_16(clip)

            final_audio = audio
            if audio.duration < target_dur:
                silence_dur = target_dur - audio.duration
                silence = AudioClip(lambda t: 0, duration=silence_dur).set_fps(44100)
                final_audio = concatenate_audioclips([audio, silence])

            if clip.duration < final_audio.duration:
                final_clip = vfx.loop(clip, duration=final_audio.duration)
            else:
                final_clip = clip.subclip(0, final_audio.duration)

            dur_final = max(0.1, final_audio.duration - AUDIO_EPSILON)
            video_final = final_clip.set_audio(final_audio).set_duration(dur_final)
            avatar = _avatar_overlay_clip(user, dur_final)
            if avatar is not None:
                video_final = CompositeVideoClip([video_final, avatar]).set_duration(dur_final).set_audio(final_audio)

            video_final.write_videofile(
                out_video,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                logger=None
            )

    finally:
        # Limpieza segura
        for p in (temp_video, temp_audio):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except:
                pass

    if not os.path.exists(out_video) or os.path.getsize(out_video) < 1000:
        raise Exception("Error crítico: el video final no fue generado")

    return out_video