import io
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import vtracer

app = Flask(__name__)

CORS(app, origins=[
    "https://printhubbr.com",
    "https://www.printhubbr.com",
    "https://printhubbr.netlify.app",
    "http://localhost:3000",
    "http://127.0.0.1:5500",
])

MAX_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_DIM   = 4000               # px — acima disso vetorização fica lenta demais


@app.route("/ping")
def ping():
    return jsonify({"ok": True})


@app.route("/vectorize", methods=["POST"])
def vectorize():
    if "imagem" not in request.files:
        return jsonify({"erro": "Nenhuma imagem enviada."}), 400

    raw = request.files["imagem"].read()
    if len(raw) > MAX_BYTES:
        return jsonify({"erro": "Imagem muito grande (máximo 15 MB)."}), 400

    # Abrir e normalizar via Pillow
    try:
        img = Image.open(io.BytesIO(raw))
        img_format = (img.format or "PNG").upper()
        if img_format == "JPEG":
            img_format = "JPEG"
        elif img_format not in ("PNG", "BMP", "JPEG"):
            img_format = "PNG"

        # Redimensionar se necessário
        w, h = img.size
        if max(w, h) > MAX_DIM:
            scale = MAX_DIM / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Converter RGBA → RGB para JPEG; manter PNG com transparência
        if img_format == "JPEG" and img.mode in ("RGBA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
            img = bg

        buf = io.BytesIO()
        img.save(buf, format=img_format)
        img_bytes = buf.getvalue()

    except Exception as e:
        return jsonify({"erro": f"Arquivo inválido: {e}"}), 400

    # Parâmetros enviados pelo frontend
    modo      = request.form.get("modo", "color")       # "color" | "binary"
    detalhe   = request.form.get("detalhe", "medio")    # "alto" | "medio" | "baixo"

    presets = {
        "alto":  {"filter_speckle": 2,  "color_precision": 8,  "corner_threshold": 45},
        "medio": {"filter_speckle": 4,  "color_precision": 6,  "corner_threshold": 60},
        "baixo": {"filter_speckle": 10, "color_precision": 4,  "corner_threshold": 75},
    }
    p = presets.get(detalhe, presets["medio"])

    try:
        svg = vtracer.convert_raw_image_to_svg(
            img_bytes,
            img_format=img_format.lower(),
            colormode=modo,
            hierarchical="stacked",
            mode="spline",
            filter_speckle=p["filter_speckle"],
            color_precision=p["color_precision"],
            layer_difference=16,
            corner_threshold=p["corner_threshold"],
            length_threshold=4.0,
            max_iterations=10,
            splice_threshold=45,
            path_precision=8,
        )
    except Exception as e:
        return jsonify({"erro": f"Erro na conversão: {e}"}), 500

    return jsonify({"svg": svg})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)

