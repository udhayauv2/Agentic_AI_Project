import json
import uuid
from app.auth import AuthContext
from app.db import get_banking_conn

def get_account_balance(auth: AuthContext, account_id: str) -> dict:
    """Look up balance and status of an account. Read-only."""
    if not auth.has_scope("read:balance"):
        return {"error": "forbidden", "hint": "Insufficient permissions to view balance."}

    with get_banking_conn() as conn:
        row = conn.execute("SELECT customer_id, balance, is_frozen FROM account WHERE id = ?", (account_id,)).fetchone()
        if not row:
            return {"error": "invalid_account", "hint": "Provide a valid account ID like ACC_100."}
        
        if auth.role == "customer" and row["customer_id"] != auth.user_id:
            return {"error": "unauthorized_account", "hint": "Cannot view accounts belonging to others."}

        return {"account_id": account_id, "balance": row["balance"], "is_frozen": bool(row["is_frozen"])}

def check_transfer_eligibility(auth: AuthContext, sender_acc: str, amount: float) -> dict:
    """Check if a transfer is valid before executing. Read-only."""
    if amount <= 0:
        return {"eligible": False, "reason": "Amount must be greater than 0."}

    with get_banking_conn() as conn:
        row = conn.execute("SELECT balance, is_frozen FROM account WHERE id = ?", (sender_acc,)).fetchone()
        if not row:
            return {"eligible": False, "reason": "Sender account does not exist."}
        if row["is_frozen"]:
            return {"eligible": False, "reason": "Sender account is frozen."}
        if row["balance"] < amount:
            return {"eligible": False, "reason": f"Insufficient funds. Current balance: {row['balance']}"}

        return {"eligible": True, "sender_acc": sender_acc, "amount": amount}

def transfer_funds(auth: AuthContext, sender_acc: str, receiver_acc: str, amount: float, idempotency_key: str) -> dict:
    """Executes money transfer. Side-effect tool guarded by idempotency and optimistic locking."""
    if not auth.has_scope("write:transfer"):
        return {"error": "forbidden", "hint": "Missing write:transfer permission."}

    with get_banking_conn() as conn:
        # Check idempotency replay
        idem = conn.execute("SELECT result FROM idempotency WHERE key = ?", (idempotency_key,)).fetchone()
        if idem:
            return json.loads(idem["result"])

        sender = conn.execute("SELECT balance, version, is_frozen, customer_id FROM account WHERE id = ?", (sender_acc,)).fetchone()
        receiver = conn.execute("SELECT id, is_frozen FROM account WHERE id = ?", (receiver_acc,)).fetchone()

        if not sender or not receiver:
            return {"error": "account_not_found", "hint": "Verify sender and receiver accounts."}
        if auth.role == "customer" and sender["customer_id"] != auth.user_id:
            return {"error": "unauthorized", "hint": "Can only debit your own account."}
        if sender["balance"] < amount:
            return {"error": "insufficient_funds", "hint": "Balance is insufficient."}

        # Optimistic locking update
        res = conn.execute(
            "UPDATE account SET balance = balance - ?, version = version + 1 WHERE id = ? AND version = ?",
            (amount, sender_acc, sender["version"])
        )
        if res.rowcount == 0:
            return {"error": "concurrency_conflict", "hint": "Balance changed concurrently. Retry."}

        conn.execute("UPDATE account SET balance = balance + ? WHERE id = ?", (amount, receiver_acc))
        
        tx_id = f"TX_{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO transaction_log (id, account_id, amount, action) VALUES (?, ?, ?, ?)",
                     (tx_id, sender_acc, -amount, "transfer_out"))

        result = {"success": True, "tx_id": tx_id, "amount": amount, "from": sender_acc, "to": receiver_acc}
        conn.execute("INSERT INTO idempotency (key, tool_name, result) VALUES (?, ?, ?)",
                     (idempotency_key, "transfer_funds", json.dumps(result)))
        return result

def admin_toggle_freeze(auth: AuthContext, account_id: str, freeze: bool) -> dict:
    """Admin-only tool to freeze or unfreeze accounts."""
    if auth.role != "admin" or not auth.has_scope("admin:freeze"):
        return {"error": "unauthorized", "hint": "Requires admin role with admin:freeze scope."}

    with get_banking_conn() as conn:
        row = conn.execute("SELECT is_frozen FROM account WHERE id = ?", (account_id,)).fetchone()
        if not row:
            return {"error": "account_not_found", "hint": "Account does not exist."}

        conn.execute("UPDATE account SET is_frozen = ? WHERE id = ?", (1 if freeze else 0, account_id))
        return {"account_id": account_id, "is_frozen": freeze, "status": "updated"}

def admin_get_audit_logs(auth: AuthContext, account_id: str) -> dict:
    """Admin-only tool to inspect audit transaction logs."""
    if auth.role != "admin":
        return {"error": "unauthorized", "hint": "Requires admin role."}

    with get_banking_conn() as conn:
        rows = conn.execute("SELECT id, amount, action, created_at FROM transaction_log WHERE account_id = ?", (account_id,)).fetchall()
        return {"account_id": account_id, "logs": [dict(r) for r in rows]}