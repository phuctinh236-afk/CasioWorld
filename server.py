# ============================================================
# ADMIN PANEL - GAME POINTS / FC ẢO
# Không có nạp tiền, rút tiền hoặc tiền thật
# ============================================================

@app.route('/admin')
@app.route('/admin/dashboard')
def admin_panel():
    username = session.get('username')

    if not username:
        return redirect('/login')

    conn = get_db_connection()
    user = conn.execute(
        "SELECT username, role FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()

    if not user or user['role'] not in ('owner', 'admin'):
        return """
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Không có quyền</title>
            <style>
                body {
                    margin: 0;
                    background: #0b1120;
                    color: white;
                    font-family: Arial, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    text-align: center;
                }
                .box {
                    background: #172136;
                    padding: 35px;
                    border-radius: 12px;
                    width: 90%;
                    max-width: 400px;
                }
                a {
                    display: inline-block;
                    margin-top: 15px;
                    padding: 10px 20px;
                    background: #f3a838;
                    color: #000;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <div class="box">
                <h2>🚫 Không có quyền truy cập</h2>
                <p>Tài khoản này không phải Admin/Owner.</p>
                <a href="/login">Đăng nhập</a>
            </div>
        </body>
        </html>
        """, 403

    return f"""
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>TX68 - Admin</title>

<style>
* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    font-family: Arial, sans-serif;
}}

body {{
    background: #0b1120;
    color: #fff;
}}

.header {{
    background: #131c2e;
    border-bottom: 1px solid #263653;
    padding: 15px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

.logo {{
    color: #f3a838;
    font-size: 20px;
    font-weight: bold;
}}

.admin-user {{
    color: #94a3b8;
    font-size: 13px;
}}

.container {{
    padding: 20px;
    max-width: 1400px;
    margin: auto;
}}

.stats {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 15px;
    margin-bottom: 20px;
}}

.stat {{
    background: #131c2e;
    border: 1px solid #263653;
    border-radius: 10px;
    padding: 20px;
}}

.stat-title {{
    color: #94a3b8;
    font-size: 13px;
    margin-bottom: 8px;
}}

.stat-value {{
    font-size: 25px;
    font-weight: bold;
    color: #f3a838;
}}

.card {{
    background: #131c2e;
    border: 1px solid #263653;
    border-radius: 10px;
    padding: 18px;
    margin-bottom: 20px;
}}

.card h2 {{
    font-size: 16px;
    color: #38bdf8;
    margin-bottom: 15px;
}}

.search {{
    width: 100%;
    padding: 11px;
    margin-bottom: 15px;
    background: #0b1120;
    border: 1px solid #334155;
    border-radius: 6px;
    color: white;
    outline: none;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}

th {{
    background: #172136;
    color: #94a3b8;
    text-align: left;
}}

th, td {{
    padding: 11px;
    border-bottom: 1px solid #263653;
}}

.fc {{
    color: #f3a838;
    font-weight: bold;
}}

.badge {{
    display: inline-block;
    padding: 4px 8px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: bold;
}}

.badge-admin {{
    background: rgba(168,85,247,.2);
    color: #c084fc;
}}

.badge-user {{
    background: rgba(56,189,248,.15);
    color: #38bdf8;
}}

.btn {{
    border: none;
    border-radius: 5px;
    padding: 6px 10px;
    cursor: pointer;
    font-weight: bold;
}}

.btn-add {{
    background: #22c55e;
    color: #000;
}}

.btn-sub {{
    background: #ef4444;
    color: #fff;
}}

.input-small {{
    width: 100px;
    padding: 7px;
    background: #0b1120;
    color: white;
    border: 1px solid #334155;
    border-radius: 5px;
}}

@media(max-width:700px) {{
    .stats {{
        grid-template-columns: 1fr;
    }}

    .container {{
        padding: 10px;
        overflow-x: auto;
    }}

    table {{
        min-width: 700px;
    }}
}}
</style>
</head>

<body>

<div class="header">
    <div class="logo">🎮 TX68 GAME ADMIN</div>

    <div class="admin-user">
        👤 {username}
        <span class="badge badge-admin">ADMIN</span>
    </div>
</div>

<div class="container">

    <div class="stats">

        <div class="stat">
            <div class="stat-title">👥 Tổng người chơi</div>
            <div class="stat-value" id="total-users">0</div>
        </div>

        <div class="stat">
            <div class="stat-title">🟢 Đang hoạt động</div>
            <div class="stat-value" id="active-users">0</div>
        </div>

        <div class="stat">
            <div class="stat-title">🪙 Tổng FC</div>
            <div class="stat-value" id="total-fc">0</div>
        </div>

    </div>


    <div class="card">

        <h2>👥 QUẢN LÝ NGƯỜI CHƠI</h2>

        <input
            class="search"
            id="search"
            placeholder="🔎 Tìm tài khoản..."
            oninput="filterUsers()"
        >

        <div style="overflow-x:auto">

            <table>

                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Tài khoản</th>
                        <th>FC</th>
                        <th>Quyền</th>
                        <th>Thay đổi FC</th>
                    </tr>
                </thead>

                <tbody id="users">
                    <tr>
                        <td colspan="5" style="text-align:center">
                            Đang tải...
                        </td>
                    </tr>
                </tbody>

            </table>

        </div>

    </div>


    <div class="card">

        <h2>📜 LỊCH SỬ HOẠT ĐỘNG</h2>

        <div style="overflow-x:auto">

            <table>

                <thead>
                    <tr>
                        <th>Thời gian</th>
                        <th>Tài khoản</th>
                        <th>Hoạt động</th>
                        <th>FC</th>
                    </tr>
                </thead>

                <tbody id="logs">
                    <tr>
                        <td colspan="4" style="text-align:center">
                            Đang tải...
                        </td>
                    </tr>
                </tbody>

            </table>

        </div>

    </div>

</div>


<script>

let allUsers = [];


async function loadUsers() {{

    try {{

        const res = await fetch('/admin/api/users');

        if (!res.ok) {{
            throw new Error('API error');
        }}

        const data = await res.json();

        allUsers = data.users || [];

        document.getElementById('total-users').textContent =
            data.total_users || 0;

        document.getElementById('active-users').textContent =
            data.active_users || 0;

        document.getElementById('total-fc').textContent =
            Number(data.total_fc || 0).toLocaleString();

        renderUsers(allUsers);

    }} catch(e) {{

        document.getElementById('users').innerHTML =
            '<tr><td colspan="5">Không thể tải dữ liệu.</td></tr>';

    }}

}}


function renderUsers(users) {{

    let html = '';

    if (!users.length) {{

        html =
            '<tr><td colspan="5" style="text-align:center">Không có người chơi.</td></tr>';

    }} else {{

        users.forEach(u => {{

            const role =
                u.role === 'owner' || u.role === 'admin'
                ? '<span class="badge badge-admin">ADMIN</span>'
                : '<span class="badge badge-user">USER</span>';

            html += `
                <tr>

                    <td>#${{u.id}}</td>

                    <td>
                        <b>${{escapeHtml(u.username)}}</b>
                    </td>

                    <td class="fc">
                        🪙 ${{Number(u.fc || 0).toLocaleString()}}
                    </td>

                    <td>
                        ${{role}}
                    </td>

                    <td>

                        <input
                            id="amount-${{u.id}}"
                            type="number"
                            class="input-small"
                            placeholder="FC"
                        >

                        <button
                            class="btn btn-add"
                            onclick="modifyFC(${{u.id}}, 1)"
                        >
                            +
                        </button>

                        <button
                            class="btn btn-sub"
                            onclick="modifyFC(${{u.id}}, -1)"
                        >
                            -
                        </button>

                    </td>

                </tr>
            `;

        }});

    }}

    document.getElementById('users').innerHTML = html;

}}


function filterUsers() {{

    const q =
        document.getElementById('search')
        .value
        .toLowerCase()
        .trim();

    const filtered = allUsers.filter(u =>
        String(u.username).toLowerCase().includes(q)
    );

    renderUsers(filtered);

}}


async function modifyFC(id, direction) {{

    const input =
        document.getElementById('amount-' + id);

    const amount =
        Number(input.value);

    if (!amount || amount <= 0) {{
        alert('Nhập số FC hợp lệ!');
        return;
    }}

    const finalAmount =
        amount * direction;

    try {{

        const res = await fetch('/admin/api/user/fc', {{

            method: 'POST',

            headers: {{
                'Content-Type': 'application/json'
            }},

            body: JSON.stringify({{
                user_id: id,
                amount: finalAmount
            }})

        }});

        const data = await res.json();

        alert(data.message || 'Đã cập nhật.');

        if (res.ok) {{
            input.value = '';
            loadUsers();
            loadLogs();
        }}

    }} catch(e) {{

        alert('Không thể kết nối máy chủ.');

    }}

}}


async function loadLogs() {{

    try {{

        const res =
            await fetch('/admin/api/logs');

        const data =
            await res.json();

        let html = '';

        if (!data.length) {{

            html =
                '<tr><td colspan="4" style="text-align:center">Chưa có lịch sử.</td></tr>';

        }} else {{

            data.forEach(item => {{

                html += `
                    <tr>

                        <td>${{escapeHtml(item.created_at || '')}}</td>

                        <td>
                            <b>${{escapeHtml(item.username || '')}}</b>
                        </td>

                        <td>
                            ${{escapeHtml(item.action || '')}}
                        </td>

                        <td class="fc">
                            ${{Number(item.amount || 0).toLocaleString()}}
                        </td>

                    </tr>
                `;

            }});

        }}

        document.getElementById('logs').innerHTML = html;

    }} catch(e) {{

        document.getElementById('logs').innerHTML =
            '<tr><td colspan="4">Không tải được lịch sử.</td></tr>';

    }}

}}


function escapeHtml(value) {{

    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');

}}


loadUsers();
loadLogs();

setInterval(() => {{
    loadUsers();
    loadLogs();
}}, 10000);

</script>

</body>
</html>
"""


# ============================================================
# ADMIN API - DANH SÁCH USER
# ============================================================

@app.route('/admin/api/users')
def admin_api_users():

    username = session.get('username')

    if not username:
        return jsonify({"message": "Chưa đăng nhập"}), 401

    conn = get_db_connection()

    admin = conn.execute(
        "SELECT role FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if not admin or admin['role'] not in ('owner', 'admin'):
        conn.close()
        return jsonify({"message": "Không có quyền"}), 403

    rows = conn.execute("""
        SELECT
            id,
            username,
            balance,
            role
        FROM users
        ORDER BY id DESC
        LIMIT 200
    """).fetchall()

    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_fc = conn.execute(
        "SELECT COALESCE(SUM(balance), 0) FROM users"
    ).fetchone()[0]

    conn.close()

    users = []

    for row in rows:
        users.append({
            "id": row["id"],
            "username": row["username"],
            "fc": row["balance"] or 0,
            "role": row["role"] or "user"
        })

    return jsonify({
        "users": users,
        "total_users": total_users,
        "active_users": 0,
        "total_fc": total_fc
    })


# ============================================================
# ADMIN API - CỘNG / TRỪ FC ẢO
# ============================================================

@app.route('/admin/api/user/fc', methods=['POST'])
def admin_api_modify_fc():

    username = session.get('username')

    if not username:
        return jsonify({
            "message": "Chưa đăng nhập"
        }), 401

    conn = get_db_connection()

    admin = conn.execute(
        "SELECT role FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if not admin or admin['role'] not in ('owner', 'admin'):
        conn.close()

        return jsonify({
            "message": "Không có quyền"
        }), 403

    data = request.get_json(silent=True) or {}

    try:
        user_id = int(data.get("user_id"))
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        conn.close()

        return jsonify({
            "message": "Dữ liệu không hợp lệ"
        }), 400

    if amount == 0:
        conn.close()

        return jsonify({
            "message": "Số FC phải khác 0"
        }), 400

    user = conn.execute(
        "SELECT id, username, balance FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()

        return jsonify({
            "message": "Không tìm thấy tài khoản"
        }), 404

    old_balance = user["balance"] or 0
    new_balance = old_balance + amount

    if new_balance < 0:
        conn.close()

        return jsonify({
            "message": "Không thể để FC âm"
        }), 400

    conn.execute(
        "UPDATE users SET balance = ? WHERE id = ?",
        (new_balance, user_id)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": (
            f"Đã {'cộng' if amount > 0 else 'trừ'} "
            f"{abs(amount):,.0f} FC cho {user['username']}."
        ),
        "old_balance": old_balance,
        "new_balance": new_balance
    })


# ============================================================
# ADMIN API - LỊCH SỬ FC
# ============================================================

@app.route('/admin/api/logs')
def admin_api_logs():

    username = session.get('username')

    if not username:
        return jsonify({
            "message": "Chưa đăng nhập"
        }), 401

    conn = get_db_connection()

    admin = conn.execute(
        "SELECT role FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if not admin or admin['role'] not in ('owner', 'admin'):
        conn.close()

        return jsonify({
            "message": "Không có quyền"
        }), 403

    # Nếu database đã có game_logs thì đọc từ đó.
    try:

        rows = conn.execute("""
            SELECT
                created_at,
                username,
                game_name,
                bet_amount,
                win_amount,
                status
            FROM game_logs
            ORDER BY id DESC
            LIMIT 100
        """).fetchall()

        result = []

        for row in rows:

            result.append({
                "created_at": row["created_at"] or "",
                "username": row["username"] or "",
                "action": row["game_name"] or "Hoạt động game",
                "amount": row["win_amount"] or 0
            })

    except Exception:

        result = []

    conn.close()

    return jsonify(result)


# ============================================================
# ADMIN API - THÔNG TIN 1 USER
# ============================================================

@app.route('/admin/api/user/<int:user_id>')
def admin_api_user(user_id):

    username = session.get('username')

    if not username:
        return jsonify({
            "message": "Chưa đăng nhập"
        }), 401

    conn = get_db_connection()

    admin = conn.execute(
        "SELECT role FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if not admin or admin['role'] not in ('owner', 'admin'):
        conn.close()

        return jsonify({
            "message": "Không có quyền"
        }), 403

    user = conn.execute("""
        SELECT
            id,
            username,
            balance,
            role
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    conn.close()

    if not user:
        return jsonify({
            "message": "Không tìm thấy tài khoản"
        }), 404

    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "fc": user["balance"] or 0,
        "role": user["role"] or "user"
    })
