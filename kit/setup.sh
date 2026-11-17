#!/usr/bin/env bash
# Prepara una sesión nueva para editar videos de Soy Petra.
set -e
pip install --break-system-packages -q rembg onnxruntime pillow numpy
which ffmpeg >/dev/null || (apt-get update -qq && apt-get install -y -qq ffmpeg)
python3 -c "from rembg import new_session; new_session('u2net_human_seg')"  # baja el modelo de personas (~170 MB)
echo "Kit listo"
