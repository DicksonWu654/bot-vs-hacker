"""The only permitted differences between the reviewed and exported paper."""

PATH_SUBSTITUTIONS = {
    "research/chain-scan": "research/chain-scan",
    "research/infra": "research/infra",
    "research/bot-re": "research/bot-re",
    "research/explainer": "research/explainer",
    "research/candidates": "research/candidates",
    "research/anon-bots": "research/anon-bots",
    "research/lineages": "research/lineages",
    "research/defiplaza-ronin": "research/defiplaza-ronin",
    "data/evolution": "data/evolution",
}


def public_paper(text):
    for old, new in PATH_SUBSTITUTIONS.items():
        text = text.replace(old, new)
    return text
