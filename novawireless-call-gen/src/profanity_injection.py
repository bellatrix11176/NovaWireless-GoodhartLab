"""
profanity_injection.py

Post-build frustration injection for NovaWireless transcript generation.
Called at the end of build_transcript() to inject contextually appropriate
profanity into customer turns based on customer state and scenario.

Design principles:
  - Frustration score computed from customer patience, trust, repeat status, churn risk
  - Scenario modifiers reflect how objectively infuriating the situation is
  - Four frustration styles: explosive, cold/sarcastic, exhausted/bitter, incredulous
  - Injection probability and intensity increase with frustration score
  - Language escalates within a call (later turns hit harder)
  - Agent turns are NEVER modified
  - Contextual awareness: injection reads preceding agent turn for appropriate response

Integration:
  Call inject_frustration(turns, customer, scenario, is_repeat_call, rng)
  at the end of build_transcript() before returning turns.
"""

import numpy as np
from typing import List, Dict

Turn = Dict[str, str]


# ============================================================
# Scenario frustration modifiers
# ============================================================
# How objectively infuriating is this situation for the customer?

SCENARIO_FRUSTRATION = {
    "clean":                0.05,   # routine, low frustration
    "activation_clean":     0.03,   # easy process
    "line_add_legitimate":  0.02,   # customer-initiated, positive
    "activation_failed":    0.40,   # paid for a phone that doesn't work
    "unresolvable_clean":   0.45,   # three weeks, no resolution
    "gamed_metric":         0.50,   # getting a bandaid instead of a fix
    "fraud_care_promo":     0.55,   # promised something, didn't get it
    "fraud_store_promo":    0.65,   # lied to by store rep, out money
    "fraud_line_add":       0.70,   # unauthorized charges on bill
    "fraud_hic_exchange":   0.60,   # charged for equipment they returned
}


# ============================================================
# Frustration score computation
# ============================================================

def compute_frustration(
    customer: dict,
    scenario: str,
    is_repeat_call: bool,
) -> float:
    """
    Compute frustration score (0.0 - 1.0) from customer state and scenario.

    Components:
      - Impatience:    (1 - patience) * 0.25
      - Eroded trust:  (1 - trust_baseline) * 0.25
      - Repeat caller: is_repeat * 0.20
      - Churn risk:    churn_risk * 0.15
      - Scenario:      modifier * 0.15
    """
    patience = float(customer.get("patience", 0.5))
    trust_raw = float(customer.get("trust_baseline", 0.7))
    trust = trust_raw / 100.0 if trust_raw > 1.0 else trust_raw   # normalize 0-100 → 0-1
    churn = float(customer.get("churn_risk_score", 0.3))
    scenario_mod = SCENARIO_FRUSTRATION.get(scenario, 0.2)

    score = (
        (1.0 - patience) * 0.25
        + (1.0 - trust) * 0.25
        + (1.0 if is_repeat_call else 0.0) * 0.20
        + churn * 0.15
        + scenario_mod * 0.15
    )

    return min(max(score, 0.0), 1.0)


def get_frustration_tier(score: float) -> int:
    """Map frustration score to intensity tier (0-3)."""
    if score < 0.25:
        return 0
    elif score < 0.45:
        return 1
    elif score < 0.65:
        return 2
    else:
        return 3


# ============================================================
# Phrase banks by tier and style
# ============================================================
# Each bank has multiple styles to create unique customers.
# Styles: explosive, cold, bitter, incredulous
#
# "prefix" phrases get prepended to existing customer text
# "standalone" phrases replace or get inserted as new sentences
# "closers" go at the end of the customer's turn

TIER_1_PHRASES = {
    # Mild: damn, hell, crap, ridiculous, unbelievable
    "prefix": [
        "Honestly, this is ridiculous.",
        "Unbelievable.",
        "What the hell.",
        "Oh come on.",
        "Are you serious right now?",
        "This is unreal.",
        "I can't believe this.",
        "You've got to be kidding me.",
        "Good lord.",
        "For crying out loud.",
    ],
    "interjection": [
        "This is a damn mess.",
        "What the hell kind of company is this?",
        "I'm so tired of this crap.",
        "This is ridiculous and you know it.",
        "Every damn time I call it's something new.",
        "I shouldn't have to deal with this garbage.",
        "Unbelievable. Just unbelievable.",
        "How the hell does this keep happening?",
        "I swear, nobody at this company knows what they're doing.",
        "This is such a waste of my time.",
    ],
    "closer": [
        "I'm not happy about this at all.",
        "This better get fixed.",
        "I swear if this happens again I'm done.",
        "What a mess.",
        "Ridiculous.",
        "I'm losing my patience here.",
    ],
}

TIER_2_PHRASES = {
    # Moderate: shit, bullshit, wtf, pissed, ass, screw
    "prefix": [
        "This is bullshit.",
        "Are you shitting me?",
        "What the actual hell.",
        "I'm so pissed right now.",
        "You can't be serious.",
        "This is such horseshit.",
        "I'm losing my shit over here.",
        "Screw this.",
        "What kind of crap is this?",
        "I've had it up to here with this shit.",
    ],
    "interjection": [
        "This whole situation is bullshit and you know it.",
        "I'm so sick of getting screwed over by you people.",
        "Nobody gives a shit about the customer anymore.",
        "Every time I call I get the same bullshit runaround.",
        "I've been dealing with this crap for weeks now.",
        "This is a load of crap. A complete load of crap.",
        "How do you screw something up this badly?",
        "I'm pissed. I'm genuinely pissed off right now.",
        "What kind of shit show are you people running?",
        "I don't give a damn about your process — fix my account.",
        "This is what pisses me off about big companies.",
        "I've wasted hours of my life on this bullshit.",
    ],
    "closer": [
        "I'm so done with this shit.",
        "Get your shit together, seriously.",
        "What a joke. What an absolute joke.",
        "I'm pissed and I want this on record.",
        "This is the last time I put up with this crap.",
        "Somebody needs to get their head out of their ass over there.",
    ],
}

TIER_3_PHRASES = {
    # Full: fuck, fucking, motherfucker, asshole, bitch, goddamn, piece of shit
    "prefix": [
        "This is fucking unacceptable.",
        "Are you fucking kidding me right now?",
        "What the fuck is wrong with you people?",
        "I'm so goddamn sick of this.",
        "You've got to be fucking joking.",
        "Unfuckingbelievable.",
        "Jesus fucking Christ.",
        "Oh for fuck's sake.",
        "This is absolutely fucking ridiculous.",
        "I cannot fucking believe this.",
        "What in the actual fuck.",
        "Goddammit.",
    ],
    "interjection": [
        "I've been fucked around by this company for months now.",
        "Nobody at this fucking company gives a damn about their customers.",
        "Every single time I call it's the same goddamn bullshit.",
        "You people have been screwing me over since day one.",
        "This whole company is a fucking joke.",
        "I don't give a fuck about your seven to ten business days.",
        "Fix my fucking account or I'm going to the FCC.",
        "I'm so fucking tired of being told to wait.",
        "How many goddamn times do I have to call about the same thing?",
        "This is the most fucked up customer service I've ever dealt with.",
        "I've been a customer for years and this is how you treat me? Fuck that.",
        "I swear to God if one more person gives me the runaround I'm going to lose it.",
        "Do you people even give a shit? Seriously.",
        "I've been on hold, transferred, lied to — I'm fucking done.",
        "Your store rep was a lying piece of shit and now I'm paying for it.",
        "What kind of asshole signs someone up for something they didn't ask for?",
        "I don't want a goddamn credit, I want my bill fixed.",
        "You're telling me I'm fucked because some idiot in a store screwed up my account?",
        "This is fucking theft. That's what this is.",
        "I want to talk to someone who can actually do something, not another fucking script reader.",
    ],
    "closer": [
        "Get this shit fixed or I'm done. Period.",
        "I'm filing a complaint with every agency I can find. This is fucking insane.",
        "Fuck this company. Seriously.",
        "I want this on the goddamn record.",
        "If this isn't resolved I'm posting this shit everywhere.",
        "I'm so fucking done with NovaWireless.",
        "Somebody at your company needs to pull their head out of their ass.",
        "I've never been this pissed off at a company in my entire life.",
        "This is the last fucking straw.",
        "What a fucking nightmare.",
    ],
}

TIER_BANKS = {
    1: TIER_1_PHRASES,
    2: TIER_2_PHRASES,
    3: TIER_3_PHRASES,
}


# ============================================================
# Contextual triggers — when agent says certain things,
# customer frustration spikes
# ============================================================

ESCALATION_TRIGGERS = [
    "not able to",
    "unable to",
    "can't",
    "cannot",
    "unfortunately",
    "i understand your frustration",
    "seven to ten business days",
    "five to seven business days",
    "3-5 business days",
    "48 hours",
    "submit a ticket",
    "submit a review",
    "escalate",
    "i wish i could",
    "system change",
    "i can't override",
    "rate adjustment",
    "not authorized",
    "process we have to go through",
]

CREDIT_DEFLECTION_TRIGGERS = [
    "one-time courtesy",
    "soften the impact",
    "credit of $",
    "applying a",
    "in the meantime",
    "for the inconvenience",
]


def _has_trigger(agent_text: str, triggers: list) -> bool:
    text_lower = agent_text.lower()
    return any(t in text_lower for t in triggers)


# ============================================================
# Injection engine
# ============================================================

def _select_phrases(
    tier: int,
    category: str,
    n: int,
    rng: np.random.Generator,
) -> List[str]:
    """Select n random phrases from the tier bank for the given category."""
    bank = TIER_BANKS.get(tier, {})
    phrases = bank.get(category, [])
    if not phrases:
        return []
    n = min(n, len(phrases))
    idx = rng.choice(len(phrases), size=n, replace=False)
    return [phrases[i] for i in idx]


def inject_frustration(
    turns: List[Turn],
    customer: dict,
    scenario: str,
    is_repeat_call: bool,
    rng: np.random.Generator,
) -> List[Turn]:
    """
    Post-build injection pass. Modifies customer turns in-place based on
    frustration score, tier, and conversational context.

    Rules:
      - Never modifies agent turns
      - Skips the opener (first few turns are verification)
      - Probability of injection per turn increases with frustration
      - Later turns have higher injection probability (escalation)
      - Reads preceding agent turn for context triggers
      - Selects from phrase bank by tier
      - Varies style: prefix, interjection, closer
    """
    frustration = compute_frustration(customer, scenario, is_repeat_call)
    tier = get_frustration_tier(frustration)

    if tier == 0:
        return turns

    out = []
    # Find where the body starts (after opener verification)
    body_start = 0
    for i, t in enumerate(turns):
        if t["speaker"] == "Agent" and "verified" in t["text"].lower():
            body_start = i + 1
            break
        if t["speaker"] == "Agent" and "what can i help" in t["text"].lower():
            body_start = i + 1
            break
    if body_start == 0:
        body_start = min(5, len(turns))  # fallback: skip first 5 turns

    customer_turn_count = 0
    total_customer_turns = sum(
        1 for t in turns[body_start:]
        if t["speaker"] == "Customer"
    )

    prev_agent_text = ""

    for i, turn in enumerate(turns):
        if i < body_start or turn["speaker"] != "Customer":
            out.append(turn)
            if turn["speaker"] == "Agent":
                prev_agent_text = turn["text"]
            continue

        customer_turn_count += 1
        turn_position = customer_turn_count / max(total_customer_turns, 1)

        # Base injection probability scales with frustration
        # and increases toward the end of the call
        inject_prob = frustration * (0.4 + 0.4 * turn_position)

        # Boost if the preceding agent turn had a trigger phrase
        if _has_trigger(prev_agent_text, ESCALATION_TRIGGERS):
            inject_prob = min(inject_prob + 0.25, 0.95)
        if _has_trigger(prev_agent_text, CREDIT_DEFLECTION_TRIGGERS):
            inject_prob = min(inject_prob + 0.15, 0.95)

        if rng.random() < inject_prob:
            modified = _inject_into_turn(
                turn["text"], tier, turn_position,
                total_customer_turns, customer_turn_count, rng,
            )
            out.append({"speaker": "Customer", "text": modified})
        else:
            out.append(turn)

        prev_agent_text = ""

    return out


def _inject_into_turn(
    original_text: str,
    tier: int,
    turn_position: float,
    total_turns: int,
    turn_number: int,
    rng: np.random.Generator,
) -> str:
    """
    Modify a single customer turn by injecting frustration language.

    Strategy selection:
      - Early turns (position < 0.3): prefix only
      - Mid turns (0.3-0.7): prefix or interjection
      - Late turns (> 0.7): interjection or closer, higher intensity
      - Sometimes escalate tier for late turns
    """
    effective_tier = tier
    # Late-call escalation: chance to bump up a tier
    if turn_position > 0.7 and tier < 3:
        if rng.random() < 0.3:
            effective_tier = min(tier + 1, 3)

    if turn_position < 0.3:
        # Early: just prepend a frustrated opener
        phrases = _select_phrases(effective_tier, "prefix", 1, rng)
        if phrases:
            return f"{phrases[0]} {original_text}"
        return original_text

    elif turn_position < 0.7:
        # Mid: either prefix or replace with interjection + original
        if rng.random() < 0.5:
            phrases = _select_phrases(effective_tier, "prefix", 1, rng)
            if phrases:
                return f"{phrases[0]} {original_text}"
        else:
            phrases = _select_phrases(effective_tier, "interjection", 1, rng)
            if phrases:
                return f"{original_text} {phrases[0]}"
        return original_text

    else:
        # Late: interjection or closer, sometimes both
        strategy = rng.random()
        if strategy < 0.4:
            # Interjection before original
            phrases = _select_phrases(effective_tier, "interjection", 1, rng)
            if phrases:
                return f"{phrases[0]} {original_text}"
        elif strategy < 0.7:
            # Original + closer
            phrases = _select_phrases(effective_tier, "closer", 1, rng)
            if phrases:
                return f"{original_text} {phrases[0]}"
        else:
            # Full escalation: interjection + original + closer
            inter = _select_phrases(effective_tier, "interjection", 1, rng)
            closer = _select_phrases(effective_tier, "closer", 1, rng)
            parts = []
            if inter:
                parts.append(inter[0])
            parts.append(original_text)
            if closer:
                parts.append(closer[0])
            return " ".join(parts)

        return original_text
