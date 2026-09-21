import uuid
import pytest
import app.db as db
from app.db import get_banking_conn
from app.auth import AuthContext
import app.tools as tools
from app.agent import generate_idempotency_key

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "BANKING_DB_PATH", str(tmp_path / "banking.db"))
    monkeypatch.setattr(db, "AGENT_DB_PATH", str(tmp_path / "agent.db"))
    db.init_dbs()

def test_crash_recovery_prevents_double_transfer():
    auth = AuthContext(
        user_id="CUST_1",
        role="customer",
        branch_id="BR_CHENNAI",
        scopes={"read:balance", "write:transfer"}
    )
    
    # 1. Check baseline balance
    with get_banking_conn() as conn:
        sender_initial = conn.execute("SELECT balance FROM account WHERE id = 'ACC_100'").fetchone()["balance"]
        receiver_initial = conn.execute("SELECT balance FROM account WHERE id = 'ACC_200'").fetchone()["balance"]

    transfer_amount = 1000.0
    # Unique run_id per test run prevents collision with previous test runs
    run_id = f"CRASH_RUN_{uuid.uuid4().hex[:8]}"
    step_seq = 2
    tool_name = "transfer_funds"
    args = {"sender_acc": "ACC_100", "receiver_acc": "ACC_200", "amount": transfer_amount}
    
    # Generate canonical idempotency key
    key = generate_idempotency_key(run_id, step_seq, tool_name, args)

    # 2. Worker A executes the transfer (new key -> executes mutation)
    res_a = tools.transfer_funds(auth, sender_acc="ACC_100", receiver_acc="ACC_200", amount=transfer_amount, idempotency_key=key)
    assert res_a["success"] is True

    # --- SIMULATE CRASH: Worker A dies before notifying agent.db ---

    # 3. Worker B claims the run and replays the same step with the same key
    res_b = tools.transfer_funds(auth, sender_acc="ACC_100", receiver_acc="ACC_200", amount=transfer_amount, idempotency_key=key)
    
    # Assert Worker B received the exact same cached result without error
    assert res_b["success"] is True
    assert res_b["tx_id"] == res_a["tx_id"]

    # 4. Verify balances in banking.db changed exactly ONCE
    with get_banking_conn() as conn:
        sender_final = conn.execute("SELECT balance FROM account WHERE id = 'ACC_100'").fetchone()["balance"]
        receiver_final = conn.execute("SELECT balance FROM account WHERE id = 'ACC_200'").fetchone()["balance"]
        idem_count = conn.execute("SELECT COUNT(*) as count FROM idempotency WHERE key = ?", (key,)).fetchone()["count"]

    assert sender_final == sender_initial - transfer_amount
    assert receiver_final == receiver_initial + transfer_amount
    assert idem_count == 1