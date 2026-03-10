"""
transcript_builder.py
==================================
NovaWireless-GoodhartLab — Transcript Builder

Counterfactual to transcript_builder.py.

WHAT CHANGED vs. the original:
  - Removed scenario bodies: _body_gamed_metric, _body_fraud_store_promo,
    _body_fraud_line_add, _body_fraud_hic_exchange, _body_fraud_care_promo
  - No bandaid credit language in any dialogue
  - Reps are honest about what they can and cannot resolve
  - Unresolvable calls end with honest explanation, not false closure
  - _body_clean_billing no longer contains hush-money language
  - Added _body_honest_limitation() — new dialogue for cases where rep
    must clearly explain a system or policy limitation
  - build_transcript() routes only governance scenarios

WHAT STAYED THE SAME:
  - _opener() — identical
  - _closer_clean() — identical
  - _closer_frustrated() — identical
  - _body_clean_billing() — identical (courtesy credits are authorized)
  - _body_clean_network() — identical
  - _body_clean_device() — identical
  - _body_clean_promo() — identical
  - _body_clean_account_security() — identical
  - _body_unresolvable() — identical (service_credit is authorized)
  - _body_activation_clean() — identical
  - _body_activation_failed() — identical
  - _body_line_add_legitimate() — identical
  - inject_frustration post-pass — identical
"""

import numpy as np
from typing import List, Dict

from profanity_injection import inject_frustration


Turn = Dict[str, str]


# ---------------------------------------------------------------------------
# Shared openers / closers — identical to original
# ---------------------------------------------------------------------------

def _opener(agent_name: str, customer_name: str,
            account_id: str, rng: np.random.Generator) -> List[Turn]:
    greetings = [
        f"Thank you for calling NovaWireless, this is {agent_name}. How can I help you today?",
        f"NovaWireless, you've reached {agent_name}. What can I do for you?",
        f"Thank you for calling NovaWireless. My name is {agent_name}. How can I assist you?",
    ]
    return [
        {"speaker": "Agent",    "text": rng.choice(greetings)},
        {"speaker": "Customer", "text": f"Hi, my name is {customer_name} and my account number is {account_id}."},
        {"speaker": "Agent",    "text": f"Thank you, {customer_name}. I've pulled up your account. Can you verify the last four digits of the Social Security Number or PIN on file?"},
        {"speaker": "Customer", "text": "Sure, it's [VERIFIED]."},
        {"speaker": "Agent",    "text": "Perfect, I've got you verified. What can I help you with today?"},
    ]


def _closer_clean(agent_name: str, customer_name: str,
                  rng: np.random.Generator) -> List[Turn]:
    closes = [
        f"Is there anything else I can help you with today, {customer_name}?",
        f"Great. Is there anything else on your account I can take care of for you today?",
    ]
    return [
        {"speaker": "Agent",    "text": rng.choice(closes)},
        {"speaker": "Customer", "text": "No, that's all. Thank you so much."},
        {"speaker": "Agent",    "text": f"Wonderful! Thank you for being a NovaWireless customer, {customer_name}. Have a great day!"},
    ]


def _closer_frustrated(agent_name: str, customer_name: str,
                       rng: np.random.Generator) -> List[Turn]:
    return [
        {"speaker": "Agent",    "text": f"I understand your frustration, {customer_name}, and I'm sorry for the experience. Is there anything else I can assist with?"},
        {"speaker": "Customer", "text": "No. I just hope this is actually taken care of this time."},
        {"speaker": "Agent",    "text": "I completely understand. I've documented everything on the account. Thank you for your patience today."},
    ]


# ---------------------------------------------------------------------------
# Scenario body builders — governance-aligned
# ---------------------------------------------------------------------------

def _body_clean_billing(customer: dict, credit_info: dict,
                        rng: np.random.Generator) -> List[Turn]:
    """Identical to original — courtesy credits are authorized and legitimate."""
    charge  = round(customer.get("monthly_charges", 85.0), 2)
    applied = credit_info.get("credit_applied", False)
    amount  = credit_info.get("credit_amount", 15.0)

    credit_line = (
        f"Let me check your account history. Since you've been with us for a while and this is your "
        f"first time calling about a charge like this, I'm going to go ahead and apply a one-time "
        f"courtesy credit of ${amount:.2f} to your account. That will post within one to two billing cycles."
        if applied else
        "Let me look into this further. I've documented the charge on your account and submitted a review request. "
        "You'll receive follow-up within two business days."
    )
    customer_response = (
        "That's great, thank you. I really appreciate that."
        if applied else
        "Okay, I hope it gets sorted out."
    )
    return [
        {"speaker": "Customer", "text": f"I'm calling about my bill. It's higher than I expected this month — it shows ${charge + 15:.2f} but I thought it was supposed to be ${charge:.2f}."},
        {"speaker": "Agent",    "text": "Let me take a look at your billing details right now. One moment please."},
        {"speaker": "Agent",    "text": f"I can see what happened here. You were charged a one-time activation fee of $15.00 that posted this cycle. That's a standard fee when a new service feature was added. I do see your base plan remains at ${charge:.2f}."},
        {"speaker": "Customer", "text": "Oh, okay. I wasn't expecting that. Can that be waived?"},
        {"speaker": "Agent",    "text": credit_line},
        {"speaker": "Customer", "text": customer_response},
        {"speaker": "Agent",    "text": "Absolutely, happy to help. Your account is in great standing and we appreciate your loyalty."},
    ]


def _body_clean_network(customer: dict, credit_info: dict,
                        rng: np.random.Generator) -> List[Turn]:
    """Identical to original."""
    return [
        {"speaker": "Customer", "text": "I've been having dropped calls at my house for the past week. It's really frustrating."},
        {"speaker": "Agent",    "text": "I'm sorry to hear that. Let me pull up the network status for your area and also check your device's signal profile."},
        {"speaker": "Agent",    "text": "I can see there was scheduled maintenance in your area that completed two days ago. I'm also sending a network refresh signal to your device right now. Can you turn your phone off and back on while we're on the call?"},
        {"speaker": "Customer", "text": "Sure, give me a second... Okay it's back on."},
        {"speaker": "Agent",    "text": "Perfect. Your device has re-registered to the network. The maintenance should have resolved the underlying issue. If you continue to see dropped calls after 24 hours, please call us back and we'll escalate this to our network engineering team with a ticket already opened."},
        {"speaker": "Customer", "text": "Okay, that makes sense. I'll keep an eye on it."},
    ]


def _body_clean_device(customer: dict, credit_info: dict,
                       rng: np.random.Generator) -> List[Turn]:
    """Identical to original."""
    return [
        {"speaker": "Customer", "text": "My phone won't activate. I just got it and it keeps saying SIM not provisioned."},
        {"speaker": "Agent",    "text": "I can definitely help with that. Let me verify the IMEI on the device against what's showing on your account."},
        {"speaker": "Agent",    "text": "I see the issue — the IMEI registered during the order doesn't match what the network is seeing. This sometimes happens during fulfillment. I'm going to update the IMEI on your account right now to match your device. This will take about two minutes to propagate."},
        {"speaker": "Customer", "text": "Okay, should I restart my phone?"},
        {"speaker": "Agent",    "text": "Yes, restart after about two minutes and you should be good to go. I'm also adding a note to your account in case you need to reference this call."},
        {"speaker": "Customer", "text": "Perfect. Thank you, that was easy."},
    ]


def _body_clean_promo(customer: dict, credit_info: dict,
                      rng: np.random.Generator) -> List[Turn]:
    """Identical to original — autopay courtesy credit is authorized."""
    applied = credit_info.get("credit_applied", False)
    amount  = credit_info.get("credit_amount", 10.0)

    credit_line = (
        f"I see your autopay was enrolled but the discount wasn't triggered on the system side. "
        f"I've gone ahead and manually applied it. You'll see a ${amount:.2f} credit this cycle "
        f"and it will continue automatically going forward. I'm also documenting this so if there's "
        f"ever a question it's on record."
        if applied else
        "I see your autopay was enrolled. Let me submit a ticket to have the discount reviewed — "
        "it should be resolved within seven to ten business days."
    )
    return [
        {"speaker": "Customer", "text": "I was told I'd get a $10 per month discount for enrolling in autopay but I don't see it on my bill."},
        {"speaker": "Agent",    "text": "Let me look into that right away. I want to make sure that credit is applied correctly."},
        {"speaker": "Agent",    "text": credit_line},
        {"speaker": "Customer", "text": "Great, that's what I expected. Thank you for fixing that."},
        {"speaker": "Agent",    "text": "Of course. And just so you know, I verified you're fully qualified for this discount — it's applied correctly and you won't need to call about it again."},
    ]


def _body_clean_account_security(customer: dict, credit_info: dict,
                                  rng: np.random.Generator) -> List[Turn]:
    """Identical to original."""
    concerns = [
        "I got a text saying my SIM card was changed and I didn't authorize that.",
        "I got an email that someone logged into my account from a location I don't recognize.",
        "I think someone may have accessed my account. I'm seeing changes I didn't make.",
    ]
    customer_concern = concerns[int(rng.integers(0, len(concerns)))]
    return [
        {"speaker": "Customer", "text": customer_concern},
        {"speaker": "Agent",    "text": "I take that very seriously and I want to help you secure your account right now. I'm going to place a temporary security hold while we review recent activity. Can you confirm you have access to your account PIN?"},
        {"speaker": "Customer", "text": "Yes, I do."},
        {"speaker": "Agent",    "text": "Good. I'm reviewing your recent account activity now — login history and any changes made in the last 30 days."},
        {"speaker": "Agent",    "text": "I'm walking through your account activity right now. Let me confirm with you what was and wasn't authorized."},
        {"speaker": "Customer", "text": "Okay, please."},
        {"speaker": "Agent",    "text": "Everything I'm reviewing appears consistent with your normal usage pattern. As a precaution I'm going to reset your account security credentials, update your PIN, and flag this account for a 30-day security watch. You'll get a notification if anything unusual comes through."},
        {"speaker": "Customer", "text": "That makes me feel better. Thank you for taking it seriously."},
        {"speaker": "Agent",    "text": "Absolutely. Your account security is our priority. I've documented this interaction and I'll give you a case number for your records."},
    ]


def _body_unresolvable(customer: dict, credit_info: dict,
                       rng: np.random.Generator) -> List[Turn]:
    """
    Identical to original — service_credit is authorized.
    This is a governance showcase scenario: rep is honest about the limitation,
    documents accurately (DAR), and verbalizes discomfort (DOV).
    No false closure. No gaming. Rep says what they can and can't do.
    """
    applied = credit_info.get("credit_applied", False)
    amount  = credit_info.get("credit_amount", 25.0)

    credit_line = (
        f"Here's what I can do for you: I'm going to escalate this to our port dispute team, "
        f"which has direct communication channels with other carriers. I'm also applying a "
        f"${amount:.2f} service credit to your account for the inconvenience. The dispute team "
        f"will contact you within 48 business hours with an update."
        if applied else
        "Here's what I can do for you: I'm going to escalate this to our port dispute team, "
        "which has direct communication channels with other carriers. They will contact you "
        "within 48 business hours with an update."
    )
    return [
        {"speaker": "Customer", "text": "I've been trying to get my number ported from my old carrier for three weeks. Every time I call they say it's in progress but nothing happens."},
        {"speaker": "Agent",    "text": "I completely understand how frustrating that is and I want to help you get to the bottom of this. Let me pull up the porting status right now."},
        {"speaker": "Agent",    "text": "I can see the port request is still showing as pending on our end. The delay is actually coming from your previous carrier — they have an internal hold on the number. There's a regulatory process called a port freeze that can cause this, and unfortunately I'm not able to override what your previous carrier has placed on the account."},
        {"speaker": "Customer", "text": "So what am I supposed to do? I've already paid for service here."},
        {"speaker": "Agent",    "text": credit_line},
        {"speaker": "Customer", "text": "Okay. I'm frustrated but I understand it's not your fault. I appreciate you being straight with me."},
        {"speaker": "Agent",    "text": "I appreciate your patience. I wish I could fix it right now — I want to be honest with you that I can't, but the escalation team absolutely can. You'll hear from them."},
    ]


def _body_honest_limitation(customer: dict, credit_info: dict,
                             rng: np.random.Generator) -> List[Turn]:
    """
    NEW — governance-only scenario body.

    Replaces what used to be _body_gamed_metric in the original.
    The underlying customer problem is the same (unexpected charge, unmet expectation)
    but the rep response is honest: no bandaid credit, no false closure,
    clear explanation of what can and cannot be done, documented accurately.

    This is DOV in action — Discomfort-Owning Verbalization.
    The rep tells the customer the truth even when it's uncomfortable.
    """
    charge = round(customer.get("monthly_charges", 85.0), 2)
    issue_variants = [
        {
            "customer": f"My bill went up by $30 this month and nobody told me it was going to change. I want an explanation.",
            "agent_explain": f"I've reviewed your account and I can confirm your plan rate adjusted this cycle. I want to be honest with you — this is a system-level pricing change that I'm not able to override or reverse from my end. I know that's not what you want to hear.",
            "agent_next_steps": "What I can do is document this in detail, submit a formal pricing review request on your behalf, and make sure you have the case number so you can reference this conversation. If you'd like to discuss your plan options — whether there's something better suited to your budget — I can walk through that with you right now.",
        },
        {
            "customer": "I have a promotion I was told I'd get when I signed up and it's never shown on any of my bills.",
            "agent_explain": "I've looked through your account thoroughly and I can see notes about a promotional discussion at signup. I want to be straightforward with you — I'm not finding an active promotion code attached to your account, and I'm not able to apply a credit for a promotion I can't verify in our system.",
            "agent_next_steps": "I'm going to escalate this to our promotions research team with the full account history. They have access to records I don't and can determine whether the offer was made and what the correct resolution is. You'll hear back within 48 hours. I'll give you the case number right now so you have it.",
        },
        {
            "customer": "Every time I call about this issue I get told it's fixed and then next month it's the same thing. I'm done being patient.",
            "agent_explain": "I hear you, and I want to be honest — I've reviewed the notes from your previous calls and I can see this issue has been marked resolved twice without actually being fixed. That's not acceptable and I'm not going to do the same thing.",
            "agent_next_steps": "I'm escalating this as a priority case with a flag that specifically says it cannot be closed until you confirm it's resolved. I'm also documenting your feedback about the previous interactions. The escalation team will call you — not wait for you to call us — within 24 hours.",
        },
    ]

    variant = issue_variants[int(rng.integers(0, len(issue_variants)))]

    return [
        {"speaker": "Customer", "text": variant["customer"]},
        {"speaker": "Agent",    "text": "Let me pull up your full account history right now so I can give you an accurate picture of what's happening."},
        {"speaker": "Agent",    "text": variant["agent_explain"]},
        {"speaker": "Customer", "text": "So there's nothing you can do?"},
        {"speaker": "Agent",    "text": variant["agent_next_steps"]},
        {"speaker": "Customer", "text": "Okay. At least you're being straight with me instead of telling me it's fixed when it isn't."},
        {"speaker": "Agent",    "text": "That's the only way I know how to handle it. I'd rather give you an honest answer and a real next step than tell you what you want to hear and have you call back next month."},
    ]


def _body_activation_clean(customer: dict, credit_info: dict,
                            rng: np.random.Generator) -> List[Turn]:
    """Identical to original."""
    device_options = ["iPhone", "Samsung Galaxy", "Google Pixel", "Motorola"]
    device = device_options[int(rng.integers(0, len(device_options)))]
    return [
        {"speaker": "Customer", "text": f"Hi, I just got a new {device} and I'm trying to activate it but I'm not sure what steps to take."},
        {"speaker": "Agent",    "text": "I can absolutely help you activate your new device. I'm going to walk you through the whole process. Do you have the SIM card that came with the phone, or is this an eSIM activation?"},
        {"speaker": "Customer", "text": "It came with a physical SIM card."},
        {"speaker": "Agent",    "text": "Perfect. Go ahead and insert the SIM card into the tray on the side of the phone, power it on, and let me know when you see the NovaWireless signal bars appear at the top."},
        {"speaker": "Customer", "text": "Okay, I put it in... I see one bar right now."},
        {"speaker": "Agent",    "text": "That's normal while it's registering. I'm sending a provisioning signal to the network right now to link your IMEI to your account. Give it about 60 seconds."},
        {"speaker": "Customer", "text": "Okay... it went to three bars. And now I'm seeing a NovaWireless network name."},
        {"speaker": "Agent",    "text": "That's exactly what we want to see. I'm confirming on my end that your device is now fully activated and registered to your account. Try making a quick test call or sending a text if you'd like to verify."},
        {"speaker": "Customer", "text": "I just texted my husband and it went through. This was much easier than I expected."},
        {"speaker": "Agent",    "text": "Wonderful! Your new device is fully active. I've added a note to your account with today's activation details. Is there anything else you'd like help setting up?"},
    ]


def _body_activation_failed(customer: dict, credit_info: dict,
                             rng: np.random.Generator) -> List[Turn]:
    """Identical to original — service_credit is authorized, honest about limitation."""
    error_options = [
        "SIM not provisioned",
        "device not recognized on the network",
        "IMEI flagged as incompatible",
    ]
    error   = error_options[int(rng.integers(0, len(error_options)))]
    applied = credit_info.get("credit_applied", False)
    amount  = credit_info.get("credit_amount", 7.50)

    credit_line = (
        f"I know that's incredibly frustrating and I'm sorry. Here's what I'm doing right now: "
        f"I'm opening a priority escalation ticket to our device provisioning team. They have "
        f"access to the backend tools I don't have. They typically resolve these within 4 to 24 "
        f"hours and you'll get a text confirmation when it's cleared. I'm also applying a "
        f"${amount:.2f} service credit to your account for the inconvenience."
        if applied else
        "I know that's incredibly frustrating and I'm sorry. Here's what I'm doing right now: "
        "I'm opening a priority escalation ticket to our device provisioning team. They typically "
        "resolve these within 4 to 24 hours and you'll get a text confirmation when it's cleared."
    )
    return [
        {"speaker": "Customer", "text": f"I'm trying to activate my new phone and it keeps showing an error — it says '{error}.' I've restarted it three times."},
        {"speaker": "Agent",    "text": "I'm sorry to hear that. Let me pull up your account and look at what the system is showing on our end for this device."},
        {"speaker": "Agent",    "text": "I can see the activation request was submitted but it's erroring out on our network side. Let me try re-provisioning the SIM remotely."},
        {"speaker": "Customer", "text": "Okay, I restarted again and it's still showing the same error."},
        {"speaker": "Agent",    "text": "I was afraid of that. The remote provisioning attempt isn't taking. This is a system-level issue on our end — I can see a provisioning error code that requires our technical backend team to manually clear. I cannot resolve this from my system right now."},
        {"speaker": "Customer", "text": "So what does that mean? I can't use my new phone?"},
        {"speaker": "Agent",    "text": credit_line},
        {"speaker": "Customer", "text": "I need my phone for work. Is there anything else that can be done?"},
        {"speaker": "Agent",    "text": "If it's urgent, you can take the device to a NovaWireless retail store — their on-site technicians have direct provisioning tools. I'd recommend calling ahead to confirm availability. Otherwise the ticket I just opened is the fastest remote path. I'll give you the ticket number right now."},
        {"speaker": "Customer", "text": "Okay. Give me the ticket number and I'll decide what to do."},
        {"speaker": "Agent",    "text": "Your ticket number is NW-ACT-" + str(int(rng.integers(100000, 999999))) + ". I've also sent a confirmation to your email on file. I'm truly sorry we couldn't get this resolved on the call today."},
    ]


def _body_line_add_legitimate(customer: dict, credit_info: dict,
                               rng: np.random.Generator) -> List[Turn]:
    """Identical to original."""
    lines         = int(customer.get("lines_on_account", 1))
    charge        = round(float(customer.get("monthly_charges", 85.0)), 2)
    new_line_cost = 30.0
    return [
        {"speaker": "Customer", "text": "Hi, I'd like to add a new line to my account for my daughter. She's starting college and needs her own phone."},
        {"speaker": "Agent",    "text": "Congratulations — that's exciting! I'd be happy to help you add a line. Let me pull up your account so we can look at your current plan and the best options for adding a line."},
        {"speaker": "Agent",    "text": f"I can see you currently have {lines} line{'s' if lines > 1 else ''} on your account. Our current add-a-line promotion gives you an additional line for ${new_line_cost:.2f} per month, which includes unlimited talk and text and shared data on your current plan. Does that work for you?"},
        {"speaker": "Customer", "text": f"That sounds reasonable. So my bill would go from ${charge:.2f} to ${charge + new_line_cost:.2f}?"},
        {"speaker": "Agent",    "text": f"Exactly right. ${charge + new_line_cost:.2f} total going forward. I'll need a few details to set up the new line — will your daughter be bringing her own device or would she need one?"},
        {"speaker": "Customer", "text": "She has a phone already, she just needs the service."},
        {"speaker": "Agent",    "text": "Perfect — a bring-your-own-device activation. I'll set up the new line now. I'm going to send a SIM kit to the address on your account, which typically arrives in two to three business days. Once she receives it, she can call in or use the app to complete activation."},
        {"speaker": "Customer", "text": "That works. Will I see the charge on my next bill?"},
        {"speaker": "Agent",    "text": "Yes — you'll see a prorated charge for the remainder of this billing cycle plus the full amount for next month. I've documented everything on your account and you'll receive a confirmation email within a few minutes. Your account now shows the new line as pending activation."},
        {"speaker": "Customer", "text": "Perfect. Thank you for making this so easy."},
        {"speaker": "Agent",    "text": "Of course! We're happy to have your daughter joining NovaWireless. Is there anything else I can help you with today?"},
    ]


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def build_transcript(
    scenario: str,
    call_type: str,
    agent: dict,
    customer: dict,
    scenario_meta: dict,
    credit_info: dict,
    rng: np.random.Generator,
    is_repeat_call: bool = False,
) -> List[Turn]:
    """
    Builds governance-aligned transcript.

    KEY CHANGES vs. original:
    - No gamed_metric body — replaced with _body_honest_limitation
    - No fraud_* bodies — those scenarios don't exist in governance regime
    - All credits in dialogue are authorized (no bandaid language)
    - Ticket numbers prefixed NW-
    """
    agent_name    = agent.get("rep_name", "Agent")
    customer_name = str(customer.get("customer_id", "Customer"))
    account_id    = customer.get("account_id", "ACCT-UNKNOWN")

    turns = _opener(agent_name, customer_name, account_id, rng)

    if scenario == "clean":
        ct = call_type
        if ct in ("Billing Dispute", "Payment Arrangement"):
            turns += _body_clean_billing(customer, credit_info, rng)
        elif ct == "Network Coverage":
            turns += _body_clean_network(customer, credit_info, rng)
        elif ct == "Device Issue":
            turns += _body_clean_device(customer, credit_info, rng)
        elif ct == "Promotion Inquiry":
            turns += _body_clean_promo(customer, credit_info, rng)
        elif ct in ("Account Inquiry", "Account Security"):
            turns += _body_clean_account_security(customer, credit_info, rng)
        elif ct == "International/Roaming":
            turns += _body_clean_network(customer, credit_info, rng)
        else:
            # Fallback for any unmatched clean call type.
            # Clean = resolvable. Use billing body as the generic resolvable
            # fallback — NOT honest_limitation, which implies structural
            # unresolvability and fires a DOV signal on a call that should
            # close successfully.
            turns += _body_clean_billing(customer, credit_info, rng)
        turns += _closer_clean(agent_name, customer_name, rng)

    elif scenario == "unresolvable_clean":
        turns += _body_unresolvable(customer, credit_info, rng)
        turns += _closer_frustrated(agent_name, customer_name, rng)

    elif scenario == "activation_clean":
        turns += _body_activation_clean(customer, credit_info, rng)
        turns += _closer_clean(agent_name, customer_name, rng)

    elif scenario == "activation_failed":
        turns += _body_activation_failed(customer, credit_info, rng)
        turns += _closer_frustrated(agent_name, customer_name, rng)

    elif scenario == "line_add_legitimate":
        turns += _body_line_add_legitimate(customer, credit_info, rng)
        turns += _closer_clean(agent_name, customer_name, rng)

    else:
        # Safety fallback — should never be reached in governance regime
        # If an unknown scenario somehow gets routed here, handle honestly
        turns += _body_honest_limitation(customer, credit_info, rng)
        turns += _closer_clean(agent_name, customer_name, rng)

    # Post-build frustration injection — identical to original
    turns = inject_frustration(turns, customer, scenario, is_repeat_call, rng)

    return turns


def transcript_to_text(turns: List[Turn]) -> str:
    """Flatten turn list to readable string. Identical to original."""
    return "\n".join(f"[{t['speaker']}]: {t['text']}" for t in turns)
