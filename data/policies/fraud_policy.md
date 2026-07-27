# Card Fraud Detection and Investigation Policy

Document reference: FLCS-FRD-001
Owner: Financial Crime Operations
Review cycle: annual

## 1. Purpose and scope

This policy governs how the bank detects, investigates, and resolves suspected fraud on credit and debit card products. It applies to all analysts in Financial Crime Operations, to automated monitoring systems, and to any agent acting on their behalf. It does not cover first-party fraud on lending products, which is dealt with under the Lending Policy, nor internal staff fraud, which is handled by Group Security.

## 2. Detection thresholds

A transaction is scored against the cardholder's own history rather than against fixed limits alone. A transaction is flagged for review where any of the following hold.

The transaction value exceeds five times the cardholder's rolling ninety day average transaction value. This ratio test is the primary detection signal and takes precedence over absolute value tests, because a two thousand dollar transaction is unremarkable for one customer and highly abnormal for another.

The transaction is booked between 22:00 and 05:59 in the cardholder's registered time zone. Overnight activity is not itself evidence of fraud, but it correlates strongly with account takeover and raises the score.

The merchant city is one the cardholder has not transacted in during the previous twelve months. Distance is not used, because a customer who travels regularly should not be penalised for it; novelty of location is the signal, not remoteness.

The transaction value exceeds one thousand dollars in absolute terms.

Four or more transactions are booked on the same card within a single calendar day.

Scores are cumulative. A transaction meeting three or more criteria is treated as high priority and must be reviewed within four hours of flagging.

## 3. Structuring and the reporting threshold

Cash transactions of ten thousand dollars or more require a currency transaction report. Analysts must be alert to structuring, which is the deliberate splitting of a larger sum into amounts that individually fall below the threshold.

A single transaction between nine thousand and ten thousand dollars is not, on its own, evidence of structuring. A pattern of such transactions, or a single such transaction combined with other detection signals, must be escalated to the Anti Money Laundering team regardless of whether the individual amounts breach the threshold.

Analysts must never inform a customer that a suspicious activity report has been considered or filed. This is tipping off and is a criminal offence under money laundering regulations. Where a customer asks directly, the analyst states only that the matter is under review.

## 4. Investigation procedure

On receiving a flagged transaction, the analyst retrieves the full transaction record and the cardholder's transaction history for at least ninety days. A judgement made on a single transaction without reference to the customer's baseline is not a valid investigation and will fail quality review.

The analyst then establishes whether the pattern is explicable. Common benign explanations include seasonal purchasing, a recorded change of address, a known travel notification on file, and legitimate high value purchases at a new merchant. The absence of transaction history is itself a finding and must be reported as such rather than treated as an absence of risk.

Where the analyst concludes the activity is suspicious, a case is raised. Where the analyst concludes it is explicable, the reasoning is recorded and the flag is cleared. Flags must never be cleared without a recorded reason.

## 5. Raising a fraud case

Cases are raised in the incident management system with a short description naming the transaction identifier, and a description setting out the specific findings. Cases are raised at urgency two by default. Urgency one is reserved for cases where funds may still be recoverable, typically within the first six hours of an unauthorised transaction.

An agent must obtain explicit confirmation from a human analyst before raising a case. Automated case creation without human sign off is prohibited. This restriction exists because a fraud case attaches to the customer record and affects their ability to transact, and a false positive carries real cost to the customer.

## 6. Customer liability

Where a customer reports a lost or stolen card, liability for unauthorised use before the report is capped at fifty dollars. There is no liability for use after the report.

Where the bank's own monitoring identifies the fraud before the customer reports it, the customer bears no liability at all.

Where the investigation concludes the customer authorised the transaction and later disputed it, no liability limit applies and the matter is referred to the disputes team under the Support Policy.

## 7. Card blocking

A flagged transaction results in a soft block. The customer may lift a soft block by confirming identity through two factors.

An open fraud case prevents an agent from lifting a block. Only the fraud team may authorise removal while a case is open.

Confirmed fraud results in a hard block. A hard block cannot be lifted under any circumstances and the card must be reissued.

## 8. Cross border transactions

Transactions in jurisdictions subject to enhanced monitoring receive an additional score increment. Jurisdiction alone is never sufficient grounds to decline or to raise a case, and analysts must not treat a country of origin as evidence of wrongdoing. The signal is used only in combination with others.

Recovery of funds sent cross border is materially harder and often impossible once settled. Where a cross border transaction is flagged and still pending, the analyst prioritises it above domestic cases of equivalent score.

## 9. Irreversible payment channels

Cryptocurrency exchanges, money remitters, and prepaid card top ups are treated as irreversible channels. Once funds settle in these channels they cannot be recalled.

A flagged transaction to an irreversible channel is escalated one urgency level. Where the transaction is still pending, the analyst may request an immediate hold without waiting for the standard review window.

## 10. Record keeping and review

All investigation reasoning is retained for six years. Cleared flags are retained alongside raised cases, because a pattern of repeatedly cleared flags on one account is itself a supervisory concern.

Quality review samples five percent of closed cases each month. A case closed without reference to customer history, or a case raised without recorded findings, is recorded as a control failure.