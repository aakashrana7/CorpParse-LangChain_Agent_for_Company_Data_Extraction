import os
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from agent_workflow import extract_company_info, save_records_to_csv
from utils import read_txt_bytes, read_pdf_bytes, ensure_dir

# ---- App setup ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
CSV_PATH = os.path.join(BASE_DIR, "company_info.csv")

# Serve / as the frontend (index.html + static assets in frontend/)
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="/")

# Increase file size limit if you want (default ~ 16MB). Example:
# app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB

ALLOWED_EXTS = {".pdf", ".txt"}


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/extract", methods=["POST"])
def extract():
    """
    Accepts form-data:
      - file: optional (.pdf or .txt)
      - essay_text: optional (string)
    Returns JSON:
      { "data": [ { "company_name": str, "founding_date": "YYYY-MM-DD", "founders": [str, ...] }, ... ] }
    Also writes backend/company_info.csv
    """
    try:
        raw_text = (request.form.get("essay_text") or "").strip()
        upfile = request.files.get("file")

        # Prefer file when both provided (but we still pass essay text if file not usable)
        if upfile and upfile.filename:
            filename = secure_filename(upfile.filename)
            _, ext = os.path.splitext(filename.lower())
            if ext not in ALLOWED_EXTS:
                return jsonify({"error": "Unsupported file type. Use .pdf or .txt"}), 400

            if ext == ".pdf":
                content = read_pdf_bytes(upfile.stream.read())
            else:  # .txt
                content = read_txt_bytes(upfile.stream.read())
        else:
            content = raw_text

        if not content:
            return jsonify({"error": "No input content provided."}), 400

        # Run the agentic extraction workflow
        records = extract_company_info(content)  # list of dicts with company_name, founding_date, founders(list)

        if not records:
            # still create empty CSV with header for consistency
            ensure_dir(os.path.dirname(CSV_PATH))
            save_records_to_csv([], CSV_PATH)
            return jsonify({"data": []}), 200

        # Persist CSV to backend/company_info.csv
        ensure_dir(os.path.dirname(CSV_PATH))
        save_records_to_csv(records, CSV_PATH)

        # Return JSON to the frontend
        return jsonify({"data": records}), 200

    except Exception as e:
        # Avoid leaking stack traces to client; log if you like
        return jsonify({"error": str(e)}), 500


# Optional: serve the CSV directly if you want a server-side download link
@app.route("/download")
def download_csv():
    directory = os.path.dirname(CSV_PATH)
    filename = os.path.basename(CSV_PATH)
    if not os.path.exists(CSV_PATH):
        return jsonify({"error": "CSV not found. Run extraction first."}), 404
    return send_from_directory(directory, filename, as_attachment=True)


if __name__ == "__main__":
    # Serve frontend assets (styles.css, script.js, etc.) from / (root)
    # Example run:  python backend/app.py
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
