from dataclasses import dataclass
from typing import Set

@dataclass
class AuthContext:
    user_id: str
    role: str           # 'customer' or 'admin'
    branch_id: str
    scopes: Set[str]    # e.g., {'read:balance', 'write:transfer', 'admin:freeze'}

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes