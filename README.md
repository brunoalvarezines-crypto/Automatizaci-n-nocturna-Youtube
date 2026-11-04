# Turno Nocturno

Fábrica automática de Shorts: recibe guiones (desde Make) y devuelve vídeos verticales de ~60 s a Telegram.

**Cada vídeo:** voz de Azure + clips verticales de Pexels + subtítulos → MP4 1080×1920.

## Cómo se activa
- **Desde Make (cada noche):** petición `POST https://api.github.com/repos/brunoalvarezines-crypto/Automatizaci-n-nocturna-Youtube/dispatches`
  con cuerpo `{"event_type": "fabricar", "client_payload": {"videos": [...]}}`.
- **A mano (prueba):** pestaña *Actions* → *Fabricar Shorts* → *Run workflow* (sin rellenar nada usa `ejemplo.json`).

## Formato de cada vídeo
```json
{
  "titulo": "…",
  "descripcion": "…",
  "etiquetas": ["psicología", "shorts"],
  "escenas": [
    {"texto": "Lo que dice la voz (español)", "busqueda": "english keywords for pexels"}
  ]
}
```
Unas 6 escenas y ~150 palabras ≈ 60 segundos.

## Secrets necesarios (Settings → Secrets and variables → Actions)
| Nombre | Qué es |
|---|---|
| `AZURE_SPEECH_KEY` | Clave del recurso Speech de Azure (plan F0 gratuito) |
| `AZURE_SPEECH_REGION` | Región del recurso, p. ej. `westeurope` |
| `PEXELS_API_KEY` | Clave de la API de Pexels |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram |
| `TELEGRAM_CHAT_ID` | ID del chat donde llegan los vídeos |

Opcional (pestaña *Variables*): `VOZ` (por defecto `es-ES-AlvaroNeural`; otra opción `es-ES-ElviraNeural`) y `VELOCIDAD` (por defecto `+8%`).

Los vídeos también quedan 7 días en *Actions → (ejecución) → Artifacts*.
