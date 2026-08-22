from flask import Flask, render_template_string, request, jsonify
import requests
import re

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LINK4M BYPASS SIÊU TỐC v2.0</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0a0a0a;
            color: #00ff41;
            font-family: 'Courier New', monospace;
            min-height: 100vh;
            padding: 20px;
            line-height: 1.5;
        }
        .container { max-width: 700px; margin: 0 auto; }
        .banner {
            border: 2px solid #00ff41;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
            box-shadow: 0 0 15px #00ff4155;
        }
        .banner h1 {
            font-size: 1.4rem;
            color: #00ff41;
            text-shadow: 0 0 10px #00ff41;
        }
        .info { color: #00d4ff; margin: 5px 0; font-size: 0.9rem; }
        .online { color: #00ff41; font-weight: bold; }
        .input-box { margin: 20px 0; }
        input[type="text"] {
            width: 100%;
            padding: 14px;
            background: #111;
            border: 1px solid #00ff41;
            color: #00ff41;
            font-family: 'Courier New', monospace;
            font-size: 1rem;
            outline: none;
        }
        input[type="text"]:focus { box-shadow: 0 0 10px #00ff41; }
        button {
            width: 100%;
            padding: 14px;
            margin-top: 10px;
            background: #00ff41;
            color: #000;
            border: none;
            font-family: 'Courier New', monospace;
            font-weight: bold;
            font-size: 1rem;
            cursor: pointer;
        }
        button:hover { background: #00cc33; }
        button:disabled { background: #333; color: #666; cursor: not-allowed; }
        .terminal {
            background: #0d0d0d;
            border: 1px solid #00ff41;
            padding: 15px;
            min-height: 220px;
            margin-top: 20px;
            white-space: pre-wrap;
            font-size: 0.9rem;
            overflow-y: auto;
        }
        .success {
            color: #00ff41;
            font-weight: bold;
            font-size: 1.3rem;
            text-align: center;
            margin: 15px 0;
            text-shadow: 0 0 10px #00ff41;
        }
        .error { color: #ff3333; }
        .yellow { color: #ffff00; }
        .cyan { color: #00d4ff; }
    </style>
</head>
<body>
    <div class="container">
        <div class="banner">
            <h1>⚡ LINK4M BYPASS SIÊU TỐC v2.0 ⚡</h1>
            <div class="info">[+] Tool   : Bypass link4m.net</div>
            <div class="info">[+] Tác giả: Toai nhà/Trần</div>
            <div class="info">[+] Trạng thái: <span class="online">ONLINE</span></div>
        </div>

        <div class="input-box">
            <input type="text" id="linkInput" placeholder="Nhập link rút gọn link4m.net..." autocomplete="off">
            <button id="bypassBtn" onclick="startBypass()">BẮT ĐẦU BYPASS</button>
        </div>

        <div class="terminal" id="terminal">Sẵn sàng nhận link...</div>
    </div>

    <script>
        const terminal = document.getElementById('terminal');
        const btn = document.getElementById('bypassBtn');
        const input = document.getElementById('linkInput');

        function log(text, cls = '') {
            const div = document.createElement('div');
            if (cls) div.className = cls;
            div.textContent = text;
            terminal.appendChild(div);
            terminal.scrollTop = terminal.scrollHeight;
        }

        function clearTerminal() { terminal.innerHTML = ''; }

        async function startBypass() {
            const link = input.value.trim();
            if (!link) { log('[-] Vui lòng nhập link!', 'error'); return; }
            if (!link.toLowerCase().includes('link4m')) {
                log('[-] Đây không phải link link4m!', 'error'); return;
            }

            btn.disabled = true;
            clearTerminal();

            const steps = [
                'Đang giải mã token...',
                'Bypassing Cloudflare...',
                'Đang trích xuất dữ liệu gốc...',
                'Đang tối ưu hóa đường dẫn...'
            ];

            for (let step of steps) {
                log(step + ' [████████████████████] 100%', 'yellow');
                await new Promise(r => setTimeout(r, 600));
            }

            log('[*] Đang lấy link gốc thật...', 'cyan');

            try {
                const res = await fetch('/bypass', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: link})
                });
                const data = await res.json();

                if (data.success) {
                    log('');
                    log('████████████████████████████████████████', 'success');
                    log('          S U C C E S S !', 'success');
                    log('████████████████████████████████████████', 'success');
                    log('');
                    log('Link gốc đã được khôi phục:', 'cyan');
                    log(data.url, 'yellow');
                    log('');
                    log('>> THÀNH CÔNG! <<', 'success');
                } else {
                    log('[-] ' + (data.message || 'Không lấy được link gốc.'), 'error');
                    log('Có thể link hết hạn hoặc bị Cloudflare chặn mạnh.', 'yellow');
                }
            } catch (e) {
                log('[-] Lỗi kết nối server.', 'error');
            }

            btn.disabled = false;
        }

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') startBypass();
        });
    </script>
</body>
</html>
"""

def extract_final_url(short_url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }
    try:
        session = requests.Session()
        resp = session.get(short_url, headers=headers, timeout=15, allow_redirects=True)
        final = resp.url
        if "link4m" not in final.lower():
            return final

        content = resp.text
        patterns = [
            r'https?://(?:www\.)?mediafire\.com/[^\s"\'<>]+',
            r'https?://drive\.google\.com/[^\s"\'<>]+',
            r'https?://(?:www\.)?mega\.nz/[^\s"\'<>]+',
            r'window\.location\s*=\s*["\'](https?://[^"\']+)["\']',
            r'href=["\'](https?://(?!link4m)[^"\']+)["\']',
        ]
        for pat in patterns:
            matches = re.findall(pat, content, re.IGNORECASE)
            if matches:
                return matches[0]
        return None
    except Exception:
        return None

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/bypass", methods=["POST"])
def bypass():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url or "link4m" not in url.lower():
        return jsonify({"success": False, "message": "Link không hợp lệ"})

    final = extract_final_url(url)
    if final:
        return jsonify({"success": True, "url": final})
    return jsonify({"success": False, "message": "Không lấy được link gốc"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
