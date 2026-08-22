from flask import Flask, render_template_string, request, jsonify
import re
import os
import time

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LINK4M BYPASS SIÊU TỐC v2.0 (Playwright)</title>
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
            font-size: 1.3rem;
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
            min-height: 240px;
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
            <div class="info">[+] Engine : Playwright + Stealth</div>
            <div class="info">[+] Tác giả: Phuc Tool VIP</div>
            <div class="info">[+] Trạng thái: <span class="online">ONLINE</span></div>
        </div>

        <div class="input-box">
            <input type="text" id="linkInput" placeholder="Nhập link rút gọn link4m.net..." autocomplete="off">
            <button id="bypassBtn" onclick="startBypass()">BẮT ĐẦU BYPASS</button>
        </div>

        <div class="terminal" id="terminal">Sẵn sàng nhận link (Playwright)...</div>
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
                'Đang khởi tạo trình duyệt ẩn...',
                'Đang giải mã token...',
                'Bypassing Cloudflare Challenge...',
                'Đang trích xuất dữ liệu gốc...',
                'Đang tối ưu hóa đường dẫn...'
            ];

            for (let step of steps) {
                log(step + ' [████████████████████] 100%', 'yellow');
                await new Promise(r => setTimeout(r, 800));
            }

            log('[*] Đang lấy link gốc thật (có thể mất 15-40 giây)...', 'cyan');

            try {
                const res = await fetch('/tool/bypass', {
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
                    if (data.detail) log(data.detail, 'yellow');
                }
            } catch (e) {
                log('[-] Lỗi kết nối server: ' + e.message, 'error');
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

def extract_with_playwright(short_url: str):
    """Dùng Playwright để vượt Cloudflare"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "Playwright chưa được cài"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                viewport={"width": 390, "height": 844},
                locale="vi-VN",
            )
            page = context.new_page()

            # Ẩn webdriver
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)

            page.goto(short_url, wait_until="domcontentloaded", timeout=45000)

            # Chờ Cloudflare challenge (nếu có)
            for _ in range(15):
                content = page.content()
                title = page.title().lower()
                if "just a moment" in title or "checking your browser" in content.lower() or "cf-challenge" in content.lower():
                    time.sleep(2)
                    continue
                break

            # Chờ thêm một chút để trang load xong
            time.sleep(3)
            final_url = page.url

            if "link4m" not in final_url.lower():
                browser.close()
                return final_url, None

            # Thử tìm link trong page
            content = page.content()
            patterns = [
                r'https?://(?:www\.)?mediafire\.com/[^\s"\'<>\\]+',
                r'https?://drive\.google\.com/[^\s"\'<>\\]+',
                r'https?://(?:www\.)?mega\.nz/[^\s"\'<>\\]+',
                r'https?://(?:www\.)?workupload\.com/[^\s"\'<>\\]+',
                r'https?://pixeldrain\.com/[^\s"\'<>\\]+',
                r'window\.location\s*=\s*["\'](https?://[^"\']+)["\']',
                r'location\.href\s*=\s*["\'](https?://[^"\']+)["\']',
            ]
            for pat in patterns:
                matches = re.findall(pat, content, re.IGNORECASE)
                if matches:
                    browser.close()
                    return matches[0], None

            browser.close()
            return None, "Không tìm thấy link gốc trong trang"
    except Exception as e:
        return None, str(e)

def extract_final_url(short_url: str):
    # Ưu tiên Playwright
    url, err = extract_with_playwright(short_url)
    if url:
        return url, None
    return None, err or "Playwright không lấy được"

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/bypass", methods=["POST"])
def bypass():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url or "link4m" not in url.lower():
        return jsonify({"success": False, "message": "Link không hợp lệ"})

    final, err = extract_final_url(url)
    if final:
        return jsonify({"success": True, "url": final})
    return jsonify({
        "success": False,
        "message": "Không lấy được link gốc",
        "detail": err or "Cloudflare quá mạnh hoặc Render hết tài nguyên"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
