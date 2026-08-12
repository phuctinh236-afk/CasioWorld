# ============================================================
# ADMIN PANEL - GAME POINTS / FC ẢO
# Không có nạp tiền, rút tiền hoặc tiền thật
# ============================================================

def get_admin_user():
    username = session.get('username')

    if not username:
        return None

    conn = get_db_connection()

    user = conn.execute(
        "SELECT id, username, role FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    conn.close()

    return user


def require_admin():
    user = get_admin_user()

    if not user:
        return None, (
            jsonify({"message": "Chưa đăng nhập"}),
            401
        )

    if user["role"] not in ("owner", "admin"):
        return None, (
            jsonify({"message": "Không có quyền"}),
            403
        )

    return user, None


# ============================================================
# ADMIN LOGIN PAGE
# ============================================================

@app.route('/admin/login')
def admin_login_page():
    return render_template('admin_login.html')


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route('/admin/login', methods=['POST'])
def admin_login():

    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({
            "message": "Vui lòng nhập tài khoản và mật khẩu."
        }), 400

    conn = get_db_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    conn.close()

    if not user:
        return jsonify({
            "message": "Tài khoản không tồn tại."
        }), 401

    if user["role"] not in ("owner", "admin"):
        return jsonify({
            "message": "Tài khoản này không có quyền Admin."
        }), 403

    # Dùng đúng cách kiểm tra password của hệ thống hiện tại.
    # Nếu server.py của bạn đang dùng check_password_hash()
    # thì giữ đoạn này.
    try:
        password_ok = check_password_hash(
            user["password"],
            password
        )
    except Exception:
        password_ok = False

    if not password_ok:
        return jsonify({
            "message": "Sai mật khẩu."
        }), 401

    session["username"] = user["username"]

    return jsonify({
        "success": True
    })


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route('/admin/logout', methods=['POST'])
def admin_logout():

    session.pop("username", None)

    return jsonify({
        "success": True
    })


# ============================================================
# ADMIN PANEL
# ============================================================

@app.route('/admin')
@app.route('/admin/dashboard')
def admin_panel():

    user = get_admin_user()

    if not user:
        return redirect('/admin/login')

    if user["role"] not in ("owner", "admin"):
        return """
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport"
                  content="width=device-width, initial-scale=1.0">
            <title>Không có quyền</title>
        </head>

        <body style="
            margin:0;
            background:#0b1120;
            color:white;
            font-family:Arial;
            display:flex;
            align-items:center;
            justify-content:center;
            height:100vh;
            text-align:center;
        ">

            <div style="
                background:#172136;
                padding:35px;
                border-radius:12px;
                width:90%;
                max-width:400px;
            ">

                <h2>🚫 Không có quyền truy cập</h2>

                <p>
                    Tài khoản này không phải Admin/Owner.
                </p>

                <a href="/admin/login"
                   style="
                       display:inline-block;
                       margin-top:15px;
                       padding:10px 20px;
                       background:#f3a838;
                       color:#000;
                       text-decoration:none;
                       border-radius:6px;
                       font-weight:bold;
                   ">
                    Đăng nhập Admin
                </a>

            </div>

        </body>
        </html>
        """, 403

    return render_template(
        "admin.html",
        username=user["username"],
        role=user["role"]
    )


# ============================================================
# ADMIN API - DANH SÁCH USER
# ============================================================

@app.route('/admin/api/users')
def admin_api_users():

    admin, error = require_admin()

    if error:
        return error

    conn = get_db_connection()

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
# ADMIN API - CỘNG / TRỪ FC
# ============================================================

@app.route('/admin/api/user/fc', methods=['POST'])
def admin_api_modify_fc():

    admin, error = require_admin()

    if error:
        return error

    data = request.get_json(silent=True) or {}

    try:
        user_id = int(data.get("user_id"))
        amount = float(data.get("amount"))
    except (TypeError, ValueError):

        return jsonify({
            "message": "Dữ liệu không hợp lệ."
        }), 400

    if amount == 0:

        return jsonify({
            "message": "Số FC phải khác 0."
        }), 400

    conn = get_db_connection()

    user = conn.execute("""
        SELECT
            id,
            username,
            balance,
            role
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    if not user:
        conn.close()

        return jsonify({
            "message": "Không tìm thấy tài khoản."
        }), 404

    # Không cho admin thường chỉnh FC của owner
    if (
        admin["role"] == "admin"
        and user["role"] == "owner"
    ):
        conn.close()

        return jsonify({
            "message": "Admin không được chỉnh FC của Owner."
        }), 403

    old_balance = float(user["balance"] or 0)
    new_balance = old_balance + amount

    if new_balance < 0:
        conn.close()

        return jsonify({
            "message": "Không thể để FC âm."
        }), 400

    conn.execute("""
        UPDATE users
        SET balance = ?
        WHERE id = ?
    """, (new_balance, user_id))

    conn.commit()
    conn.close()

    action = "Cộng FC" if amount > 0 else "Trừ FC"

    return jsonify({
        "success": True,
        "message": (
            f"{action} {abs(amount):,.0f} FC "
            f"cho {user['username']} thành công."
        ),
        "old_balance": old_balance,
        "new_balance": new_balance
    })


# ============================================================
# ADMIN API - LỊCH SỬ GAME
# ============================================================

@app.route('/admin/api/logs')
def admin_api_logs():

    admin, error = require_admin()

    if error:
        return error

    conn = get_db_connection()

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

    except Exception:

        conn.close()

        return jsonify([])

    result = []

    for row in rows:

        result.append({
            "created_at": row["created_at"] or "",
            "username": row["username"] or "",
            "action": row["game_name"] or "Hoạt động game",
            "amount": row["win_amount"] or 0,
            "bet_amount": row["bet_amount"] or 0,
            "status": row["status"] or ""
        })

    conn.close()

    return jsonify(result)


# ============================================================
# ADMIN API - THÔNG TIN USER
# ============================================================

@app.route('/admin/api/user/<int:user_id>')
def admin_api_user(user_id):

    admin, error = require_admin()

    if error:
        return error

    conn = get_db_connection()

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
            "message": "Không tìm thấy tài khoản."
        }), 404

    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "fc": user["balance"] or 0,
        "role": user["role"] or "user"
    })
