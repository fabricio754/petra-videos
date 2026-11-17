# Kit de edición de Soy Petra (plantilla «Petra Postcard»)

Lo usa el agente **Editor**. Las instrucciones completas están en Notion, en la página «🎬 Editor».

## Preparar la sesión

```bash
git clone --depth 1 https://github.com/fabricio754/petra-videos
bash petra-videos/kit/setup.sh
```

## Editar un video

```bash
python3 petra-videos/kit/editar.py trabajo.json
```

`ejemplo_trabajo.json` es el video v2 aprobado («¿Alguien más se siente así?»). Copia su forma.

El script hace esto:
1. Monta las tomas en 1080x1920 a 30 fps y corrige el HDR solo (PQ y HLG de iPhone).
2. Aplica los efectos Postcard (`postcard.py`):
   - cifras gigantes detrás de Del Mar (`big`);
   - íconos rosados con palabras clave (`icons`);
   - tarjeta final tipo notificación (`end`).
3. Pone subtítulos: gancho grande arriba y frases de máximo 3 palabras abajo. En los tramos de `ocultar` quita la cifra, porque ya se ve grande.
4. Mezcla la voz con la música (que baja sola cuando hay voz) y normaliza a -14 LUFS.

Una corrida tarda unos 4 minutos por video de 20 s, casi todo en la máscara de persona.

## Íconos disponibles (`icons/`)

baby-carriage, briefcase, building, calendar, cash, check, clock, coffee, confetti, door, heart, home, key, map-pin, message-circle, moneybag, phone, qrcode, send, sparkles, star, thumb-up, users, wallet

Para crear más (Tabler Icons, en rosado #FF5C93):

```bash
npm pack @tabler/icons && tar xzf tabler-icons-*.tgz
sed -e 's/stroke="currentColor"/stroke="#FF5C93"/' -e 's/stroke-width="2"/stroke-width="1.6"/' package/icons/outline/NOMBRE.svg > x.svg
rsvg-convert -w 300 -h 300 x.svg -o petra-videos/kit/icons/NOMBRE.png
```

## Reglas que el Editor revisa antes de publicar

- Nunca la cara del bebé.
- Solo se dice «$50.000 por visita» y «$100.000 por conjunto activado».
- Música solo con licencia (Pixabay).
- La creadora es «Del Mar».
