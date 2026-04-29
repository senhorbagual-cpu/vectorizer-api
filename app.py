import io
import os
import traceback
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

MAX_BYTES = 15 * 1024 * 1024
MAX_DIM   = 3000


@app.route("/ping")
def ping():
    return jsonify({"ok": True})


@app.route("/test")
def test():
    """Endpoint de diagnóstico — testa vtracer com imagem mínima."""
    try:
        img = Image.new("RGB", (20, 20), (233, 69, 96))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        svg = vtracer.convert_raw_image_to_svg(
            buf.getvalue(),
            img_format="png",
            colormode="color",
            hierarchical="stacked",
            mode="spline",
            filter_speckle=4,
            color_precision=6,
            layer_difference=16,
            corner_threshold=60,
            length_threshold=4.0,
            max_iterations=10,
            splice_threshold=45,
            path_precision=8,
        )
        return jsonify({"ok": True, "svg_len": len(svg)})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e), "trace": traceback.format_exc()}), 500


@app.route("/vectorize", methods=["POST"])
def vectorize():
    if "imagem" not in request.files:
        return jsonify({"erro": "Nenhuma imagem enviada."}), 400

    raw = request.files["imagem"].read()
    if len(raw) > MAX_BYTES:
        return jsonify({"erro": "Imagem muito grande (máximo 15 MB)."}), 400

    try:
        img = Image.open(io.BytesIO(raw))
        img_format = (img.format or "PNG").upper()
        if img_format not in ("PNG", "BMP", "JPEG"):
            img_format = "PNG"

        # Redimensionar se necessário
        w, h = img.size
        if max(w, h) > MAX_DIM:
            scale = MAX_DIM / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Normalizar modo de cor
        if img_format == "JPEG":
            if img.mode in ("RGBA", "P", "LA"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    bg.paste(img, mask=img.split()[3])
                else:
                    bg.paste(img.convert("RGB"))
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
        else:
            # PNG/BMP — converter para RGB ou RGBA
            if img.mode not in ("RGB", "RGBA", "L"):
                img = img.convert("RGBA")

        buf = io.BytesIO()
        img.save(buf, format=img_format)
        img_bytes = buf.getvalue()

    except Exception as e:
        return jsonify({"erro": f"Arquivo inválido: {e}"}), 400

    modo    = request.form.get("modo", "color")
    detalhe = request.form.get("detalhe", "medio")

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
        return jsonify({"erro": f"Erro na conversão: {e}", "trace": traceback.format_exc()}), 500

    return jsonify({"svg": svg})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)

