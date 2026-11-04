"""Rule registry and evaluation. Rules are plain functions of a Context.

A rule returns a list of findings (empty = passed) or raises NotEvaluated with
the reason. Limits come only from the selected profile.
"""

from dataclasses import dataclass, field

from ..models import Finding, Mark, RuleOutcome, ERROR, WARNING, INFO, SEVERITIES, PASSED, FAILED, NOT_EVALUATED

REGISTRY = {}


class NotEvaluated(Exception):
    """The rule could not be checked; the message says why."""


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    process: str              # 'geometry', 'laser', ...
    description: str
    uses: str                 # geometry the rule reads
    default_severity: str
    needs_limit: bool
    reference: str
    assumptions: str
    function: object = field(compare=False, repr=False)


def rule(id, name, process, *, description, uses, severity, needs_limit=True, reference='', assumptions=''):
    def register(function):
        if id in REGISTRY:
            raise ValueError(f'Yinelenen kural kimliği: {id}')
        REGISTRY[id] = Rule(id, name, process, description, uses, severity, needs_limit, reference, assumptions, function)
        return function
    return register


@dataclass
class Context:
    topology: object
    drawing: object
    profile: object
    thickness: float | None
    material: str
    accuracy: float = .01                 # mm, measurement / flattening accuracy
    stop: object = None

    def config(self, rule_id):
        return self.profile.rules.get(rule_id, {})

    def severity(self, rule):
        value = self.config(rule.id).get('severity', rule.default_severity)
        return value if value in SEVERITIES else rule.default_severity

    def limit(self, rule):
        """max(min_mm, factor_t * t). A thickness factor needs a thickness."""
        cfg = self.config(rule.id)
        minimum, factor = cfg.get('min_mm'), cfg.get('factor_t')
        values = []
        if factor:
            if self.thickness is None:
                raise NotEvaluated('Sınır sac kalınlığına bağlı; kalınlık girilmedi.')
            values.append(float(factor) * self.thickness)
        if minimum is not None:
            values.append(float(minimum))
        if not values:
            raise NotEvaluated('Seçili profil bu kural için sınır değeri tanımlamıyor.')
        return max(values)

    def finding(self, rule, message, suggestion, *, measured=None, limit=None, marks=(), entities=(), part=''):
        return Finding(rule.id, rule.name, rule.process, self.severity(rule), message, suggestion,
                       None if measured is None else round(float(measured), 6),
                       None if limit is None else round(float(limit), 6),
                       entities=list(entities), marks=list(marks), part=part)

    def checkpoint(self):
        if self.stop is not None and self.stop.is_set():
            raise InterruptedError('Analiz durduruldu.')


def evaluate(context, progress=None):
    """Run the profile's enabled rules. Returns (outcomes, findings)."""
    outcomes, findings = [], []
    enabled = [REGISTRY[rid] for rid, cfg in context.profile.rules.items()
               if rid in REGISTRY and cfg.get('enabled', True)]
    for index, r in enumerate(enabled, 1):
        context.checkpoint()
        if progress:
            progress(index, len(enabled), f'{r.id} · {r.name}')
        limit, reason = None, ''
        try:
            if r.needs_limit:
                limit = context.limit(r)
            found = r.function(context, r, limit)
        except NotEvaluated as error:
            outcomes.append(RuleOutcome(r.id, r.name, r.process, NOT_EVALUATED, None, reason=str(error),
                                        reference=r.reference, assumptions=r.assumptions))
            continue
        findings.extend(found)
        outcomes.append(RuleOutcome(r.id, r.name, r.process, FAILED if found else PASSED,
                                    None if limit is None else round(limit, 6), reason=r.uses,
                                    reference=context.config(r.id).get('reference') or r.reference,
                                    assumptions=r.assumptions, findings=len(found)))
    return outcomes, findings


__all__ = ['rule', 'Rule', 'Context', 'NotEvaluated', 'evaluate', 'REGISTRY', 'Mark', 'ERROR', 'WARNING', 'INFO']
