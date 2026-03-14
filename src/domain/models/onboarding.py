from enum import Enum


class OnboardingStep(Enum):
    """Represents the current step of the user onboarding flow"""
    NEEDS_YNAB_CONNECTION = "needs_ynab_connection"  # User needs to authorize YNAB (OAuth)
    NEEDS_BUDGET = "needs_budget"                    # User has authorized but no budget selected
    NEEDS_ACCOUNT = "needs_account"                  # Budget selected but no default account selected
    COMPLETE = "complete"                            # Fully configured and ready to go
