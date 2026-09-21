import hashlib
import json
import uuid
from app.auth import AuthContext
from app.db import get_agent_conn
import app.tools as tools

def generate_idempotency_key(run_id: str, step: int, tool_name: str, args: dict) -> str:
    canonical = json.dumps([run_id, step, tool_name, sorted(args.items())], separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()

class ReadSpecialist:
    """Read-only specialist. Cannot alter data under any circumstances."""
    def __init__(self, auth: AuthContext):
        self.auth = auth
        self.tools = {
            "get_account_balance": tools.get_account_balance,
            "check_transfer_eligibility": tools.check_transfer_eligibility,
        }

    def execute(self, tool_name: str, args: dict) -> dict:
        if tool_name not in self.tools:
            return {"error": "tool_not_permitted", "hint": "ReadSpecialist can only query read-only tools."}
        return self.tools[tool_name](self.auth, **args)


class TransferSpecialist:
    """Mutation specialist. Executes fund transfers protected by idempotency."""
    def __init__(self, auth: AuthContext):
        self.auth = auth
        self.tools = {
            "transfer_funds": tools.transfer_funds
        }

    def execute(self, tool_name: str, args: dict, idempotency_key: str) -> dict:
        if tool_name not in self.tools:
            return {"error": "tool_not_permitted", "hint": "TransferSpecialist only executes transfers."}
        args["idempotency_key"] = idempotency_key
        return self.tools[tool_name](self.auth, **args)


class BankingSupervisor:
    """Supervisor agent that routes intents to isolated specialists."""
    def __init__(self, auth: AuthContext, thread_id: str):
        self.auth = auth
        self.thread_id = thread_id
        self.reader = ReadSpecialist(auth)
        self.writer = TransferSpecialist(auth)

    def run(self, user_prompt: str, max_steps: int = 5) -> str:
        run_id = f"RUN_{uuid.uuid4().hex[:8]}"
        with get_agent_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO thread (id, user_id) VALUES (?, ?)", (self.thread_id, self.auth.user_id))
            conn.execute("INSERT INTO run (id, thread_id, status) VALUES (?, ?, 'running')", (run_id, self.thread_id))
            last_seq = conn.execute("SELECT MAX(seq) as max_seq FROM message WHERE thread_id = ?", (self.thread_id,)).fetchone()["max_seq"]
            seq = (last_seq or 0) + 1
            conn.execute("INSERT INTO message (thread_id, seq, role, content) VALUES (?, ?, 'user', ?)",
                         (self.thread_id, seq, user_prompt))

        print(f"\n[Supervisor {run_id}] Prompt: '{user_prompt}'")

        for step in range(max_steps):
            seq += 1
            plan = self._plan(user_prompt, step)

            if not plan:
                answer = "Done: Transaction workflow completed."
                with get_agent_conn() as conn:
                    conn.execute("INSERT INTO message (thread_id, seq, role, content) VALUES (?, ?, 'assistant', ?)",
                                 (self.thread_id, seq, answer))
                    conn.execute("UPDATE run SET status = 'succeeded' WHERE id = ?", (run_id,))
                return answer

            specialist = plan["specialist"]
            tool_name = plan["tool"]
            tool_args = plan["args"]

            print(f"  Supervisor -> Delegating to {specialist} ({tool_name})")

            if specialist == "ReadSpecialist":
                result = self.reader.execute(tool_name, tool_args)
            elif specialist == "TransferSpecialist":
                key = generate_idempotency_key(run_id, step, tool_name, tool_args)
                result = self.writer.execute(tool_name, tool_args, idempotency_key=key)
            else:
                result = {"error": "unknown_specialist", "hint": "Escalate to admin."}

            with get_agent_conn() as conn:
                conn.execute("INSERT INTO tool_call (run_id, tool_name, args, result) VALUES (?, ?, ?, ?)",
                             (run_id, tool_name, json.dumps(tool_args), json.dumps(result)))
                conn.execute("INSERT INTO message (thread_id, seq, role, content) VALUES (?, ?, 'tool', ?)",
                             (self.thread_id, seq, json.dumps(result)))

            print(f"    {specialist} result: {result}")

            if "error" in result and result["error"] in ("forbidden", "unauthorized"):
                return f"Denied: {result['hint']}"

        with get_agent_conn() as conn:
            conn.execute("UPDATE run SET status = 'failed' WHERE id = ?", (run_id,))
        return "Circuit Breaker: Step limit reached."

    def _plan(self, prompt: str, step: int):
        p = prompt.lower()
        if "balance" in p and step == 0:
            return {"specialist": "ReadSpecialist", "tool": "get_account_balance", "args": {"account_id": "ACC_100"}}
        if "transfer" in p or "send" in p:
            if step == 0:
                return {"specialist": "ReadSpecialist", "tool": "check_transfer_eligibility", "args": {"sender_acc": "ACC_100", "amount": 2500.0}}
            if step == 1:
                return {"specialist": "TransferSpecialist", "tool": "transfer_funds", "args": {"sender_acc": "ACC_100", "receiver_acc": "ACC_200", "amount": 2500.0}}
        return None