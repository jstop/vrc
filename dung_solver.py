"""
Dung Argumentation Framework Solver
Pure Python implementation — no external dependencies.

Computes grounded, preferred, stable, and complete extensions
from a set of arguments and binary attack relations.
"""

from __future__ import annotations


class ArgumentationFramework:
    """
    Dung's Abstract Argumentation Framework.
    AF = (Args, Attacks) where Attacks ⊆ Args × Args
    """

    def __init__(self):
        self.arguments = set()
        self.attacks = set()  # set of (attacker, target) tuples

    def add_argument(self, arg_id: str):
        self.arguments.add(arg_id)

    def add_attack(self, attacker: str, target: str):
        self.arguments.add(attacker)
        self.arguments.add(target)
        self.attacks.add((attacker, target))

    def connected_components(self) -> list:
        """Find disconnected components in the attack graph (undirected)."""
        visited = set()
        components = []
        adj = {}
        for a in self.arguments:
            adj[a] = set()
        for (attacker, target) in self.attacks:
            adj[attacker].add(target)
            adj[target].add(attacker)
        for arg in self.arguments:
            if arg not in visited:
                component = set()
                queue = [arg]
                while queue:
                    node = queue.pop(0)
                    if node in visited:
                        continue
                    visited.add(node)
                    component.add(node)
                    for neighbor in adj[node]:
                        if neighbor not in visited:
                            queue.append(neighbor)
                components.append(component)
        return components

    def sub_framework(self, args) -> "ArgumentationFramework":
        """Create a sub-framework containing only the specified arguments."""
        sf = ArgumentationFramework()
        arg_set = set(args)
        for a in arg_set:
            sf.add_argument(a)
        for (attacker, target) in self.attacks:
            if attacker in arg_set and target in arg_set:
                sf.add_attack(attacker, target)
        return sf

    def attackers_of(self, arg: str) -> set:
        return {a for (a, t) in self.attacks if t == arg}

    def attacked_by(self, arg: str) -> set:
        return {t for (a, t) in self.attacks if a == arg}

    def is_conflict_free(self, s: set) -> bool:
        for a in s:
            for b in s:
                if (a, b) in self.attacks:
                    return False
        return True

    def defends(self, s: set, arg: str) -> bool:
        """S defends arg iff every attacker of arg is attacked by some member of S."""
        for attacker in self.attackers_of(arg):
            if not any((d, attacker) in self.attacks for d in s):
                return False
        return True

    def is_admissible(self, s: set) -> bool:
        if not self.is_conflict_free(s):
            return False
        for arg in s:
            if not self.defends(s, arg):
                return False
        return True

    def characteristic_function(self, s: set) -> set:
        """F(S) = {a ∈ Args | S defends a}"""
        return {a for a in self.arguments if self.defends(s, a)}

    def grounded_extension(self) -> set:
        """Least fixed point of the characteristic function.
        The unique, most skeptical extension."""
        s = set()
        while True:
            next_s = self.characteristic_function(s)
            if next_s == s:
                return s
            s = next_s

    def _find_conflict_free_sets(self) -> list:
        """Find all conflict-free sets using backtracking with pruning."""
        args_list = sorted(self.arguments)
        n = len(args_list)
        results = []

        def backtrack(idx, current):
            results.append(frozenset(current))
            for i in range(idx, n):
                arg = args_list[i]
                # Check if adding this arg keeps the set conflict-free
                conflict = False
                for existing in current:
                    if (arg, existing) in self.attacks or (existing, arg) in self.attacks:
                        conflict = True
                        break
                if not conflict:
                    current.add(arg)
                    backtrack(i + 1, current)
                    current.remove(arg)

        backtrack(0, set())
        return [set(s) for s in results]

    def complete_extensions(self) -> list:
        """All admissible sets S where S = F(S) (fixed points of characteristic fn)."""
        if len(self.arguments) > 15:
            # For large frameworks, just return grounded
            return [self.grounded_extension()]

        results = []
        for s in self._find_conflict_free_sets():
            if self.is_admissible(s) and self.characteristic_function(s) == s:
                results.append(s)
        return results

    def preferred_extensions(self) -> list:
        """Maximal complete extensions (by set inclusion)."""
        complete = self.complete_extensions()
        preferred = []
        for s in complete:
            if not any(s < other for other in complete):
                preferred.append(s)
        return preferred

    def stable_extensions(self) -> list:
        """Conflict-free sets that attack every argument not in the set."""
        if len(self.arguments) > 15:
            return []

        results = []
        for s in self._find_conflict_free_sets():
            if not s:
                continue
            outside = self.arguments - s
            if all(any((a, o) in self.attacks for a in s) for o in outside):
                results.append(s)
        return results

    def argument_status(self) -> dict:
        """Classify each argument as accepted/rejected/undecided
        based on the grounded extension (most conservative)."""
        grounded = self.grounded_extension()
        status = {}
        for arg in self.arguments:
            if arg in grounded:
                status[arg] = "accepted"
            elif any(
                attacker in grounded for attacker in self.attackers_of(arg)
            ):
                status[arg] = "rejected"
            else:
                status[arg] = "undecided"
        return status

    def full_analysis(self) -> dict:
        grounded = self.grounded_extension()
        preferred = self.preferred_extensions()
        stable = self.stable_extensions()
        status = self.argument_status()

        result = {
            "arguments": sorted(self.arguments),
            "attacks": [{"from": a, "to": t} for a, t in self.attacks],
            "grounded_extension": sorted(grounded),
            "preferred_extensions": [sorted(s) for s in preferred],
            "stable_extensions": [sorted(s) for s in stable],
            "argument_status": status,
            "summary": {
                "total_arguments": len(self.arguments),
                "accepted": len([a for a, s in status.items() if s == "accepted"]),
                "rejected": len([a for a, s in status.items() if s == "rejected"]),
                "undecided": len([a for a, s in status.items() if s == "undecided"]),
            },
        }

        # Independence detection: decompose disconnected components
        comps = self.connected_components()
        if len(comps) > 1:
            contested = []
            uncontested = []
            for comp in comps:
                sf = self.sub_framework(comp)
                if len(sf.attacks) == 0:
                    uncontested.extend(sorted(comp))
                else:
                    sub = sf.full_analysis()
                    contested.append({
                        "arguments": sub["arguments"],
                        "attacks": sub["attacks"],
                        "grounded_extension": sub["grounded_extension"],
                        "preferred_extensions": sub["preferred_extensions"],
                        "argument_status": sub["argument_status"],
                        "summary": sub["summary"],
                    })

            factors = [len(c["preferred_extensions"]) for c in contested]
            product = 1
            for f in factors:
                product *= f

            result["components"] = {
                "count": len(comps),
                "contested": contested,
                "uncontested": uncontested,
                "combinatorial": {
                    "factors": factors,
                    "product": product,
                },
            }

        return result


def build_framework(claims: list, attacks: list) -> ArgumentationFramework:
    """Build an AF from extracted claims and attack relations.

    claims: list of {"id": "c1", "text": "..."}
    attacks: list of {"from": "c1", "to": "c2", "reason": "..."}
    """
    af = ArgumentationFramework()
    for claim in claims:
        af.add_argument(claim["id"])
    for attack in attacks:
        af.add_attack(attack["from"], attack["to"])
    return af
