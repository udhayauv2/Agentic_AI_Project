import uuid
import pytest
from app.db import init_dbs, get_agent_conn
from app.auth import AuthContext
import app.tools as tools

@pytest.fixture(autouse=True)
def setup_db():
    init_dbs()

def test_customer_cannot_view_others_balance():
    auth = AuthContext(user_id="CUST_1", role="customer", branch_id="BR_CHENNAI", scopes={"read:balance"})
    res = tools.get_account_balance(auth, "ACC_200")
    assert res.get("error") == "unauthorized_account"

def test_customer_cannot_freeze_account():
    auth = AuthContext(user_id="CUST_1", role="customer", branch_id="BR_CHENNAI", scopes={"read:balance"})
    res = tools.admin_toggle_freeze(auth, "ACC_100", freeze=True)
    assert res.get("error") == "unauthorized"

def test_database_paths_work_from_any_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_dbs()
    auth = AuthContext(user_id="CUST_1", role="customer", branch_id="BR_CHENNAI", scopes={"read:balance"})
    assert tools.get_account_balance(auth, "ACC_100").get("account_id") == "ACC_100"

def test_transfer_rejects_invalid_amount_and_unauthorized_sender():
    auth = AuthContext(user_id="CUST_1", role="customer", branch_id="BR_CHENNAI", scopes={"write:transfer"})
    assert tools.transfer_funds(auth, "ACC_100", "ACC_200", 0, "invalid-amount").get("error") == "invalid_amount"
    eligibility = tools.check_transfer_eligibility(auth, "ACC_200", 1)
    assert eligibility == {"eligible": False, "reason": "Cannot debit accounts belonging to others."}

def test_messages_are_append_only():
    # Generate a unique thread ID so reruns never collide on UNIQUE(thread_id, seq)
    test_thread = f"TH_TEST_{uuid.uuid4().hex[:8]}"

    with get_agent_conn() as conn:
        conn.execute("INSERT INTO thread (id, user_id) VALUES (?, ?)", (test_thread, "CUST_1"))
        conn.execute("INSERT INTO message (thread_id, seq, role, content) VALUES (?, 1, 'user', 'hello')", (test_thread,))

        # Verify the trigger actively raises an error when an UPDATE is attempted
        with pytest.raises(Exception) as exc_info:
            conn.execute("UPDATE message SET content = 'tampered' WHERE thread_id = ? AND seq = 1", (test_thread,))
        
        assert "Messages are append-only" in str(exc_info.value)