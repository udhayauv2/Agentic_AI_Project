from app.db import init_dbs
from app.auth import AuthContext
from app.agent import BankingSupervisor

if __name__ == "__main__":
    init_dbs()

    cust_auth = AuthContext(
        user_id="CUST_1",
        role="customer",
        branch_id="BR_CHENNAI",
        scopes={"read:balance", "write:transfer"}
    )

    supervisor = BankingSupervisor(cust_auth, thread_id="TH_SUPERVISOR_01")
    
    # 1. Inquiry delegation
    res1 = supervisor.run("Check my balance")
    print("Response:", res1)

    # 2. Multi-step delegation (ReadSpecialist -> TransferSpecialist)
    res2 = supervisor.run("Transfer 2500 to ACC_200")
    print("Response:", res2)