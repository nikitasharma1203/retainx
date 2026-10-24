# Personas (behavioural, cutoff 2011-12-01)

Built with `python -m src.personas --cutoff 2011-12-01 --k 5` on 5,824 customers. These describe **behaviour only**.
The dataset has no demographics, ages or motives, and none are implied. Figures are medians per segment.
The actions are suggestions, not tested interventions.

**Why k = 5.** Silhouette favours fewer segments (0.315 at k = 2, 0.338 at k = 3, 0.272 at k = 5), so the structure is
moderate at any k. k = 5 was chosen because it splits the high-value group, which carries most of the revenue, into two
groups that need different handling. k = 3 is shown at the end as the coarse view.

| Persona | Customers | Share of revenue | Last order | Orders | Spend | Avg order | Tenure |
|---|---|---|---|---|---|---|---|
| Top accounts | 1,020 (18%) | 74% | 21 days ago | 14 | £5,767 | £439 | 682 days |
| Solid regulars | 1,527 (26%) | 14% | 56 days ago | 5 | £1,408 | £253 | 579 days |
| Recent newcomers | 1,376 (24%) | 6% | 45 days ago | 2 | £462 | £268 | 120 days |
| Lapsed repeat buyers | 993 (17%) | 6% | 423 days ago | 2 | £661 | £348 | 580 days |
| Lapsed small one-timers | 908 (16%) | 1% | 425 days ago | 1 | £167 | £131 | 506 days |

The headline: the top two groups (44% of customers) generate 88% of revenue, and the two lapsed groups (33% of customers) generate 7%.

## Top accounts
**Who:** 18% of customers and 74% of revenue. They order often (14 orders), have the largest orders (£439), and bought 21 days ago.
**Need:** continuity. Losing one costs more than losing any customer from the three groups below.
**Action:** put them first on the health score. Any drop to Amber or Red gets a personal follow-up within a week, not a bulk email.

## Solid regulars
**Who:** 26% of customers, 14% of revenue. Five orders, recent, but with a lower average order (£253) than the top accounts (£439).
**Need:** a reason to buy more per order or more often.
**Action:** test a bundle or volume offer aimed at raising order value, with a holdout group so the effect can be measured.

## Recent newcomers
**Who:** 24% of customers, 6% of revenue. Two orders, a median of 120 days since joining, still buying.
**Need:** a third order. The regulars' median is five.
**Action:** a post-order campaign aimed at the third order, with a holdout.

## Lapsed repeat buyers
**Who:** 17% of customers, 6% of revenue. Two orders at a decent order value (£348), but the last one was about 14 months ago.
**Need:** a reason to come back. They are the best win-back candidates among the lapsed, because they have already bought twice.
**Action:** one targeted win-back message, tested against a holdout before any wider spend.

## Lapsed small one-timers
**Who:** 16% of customers, 1% of revenue. One order of about £167, last bought 425 days ago.
**Need:** nothing worth the cost.
**Action:** no CRM spend. Exclude them from campaigns. **Too low in value to act on**, although the group is large (908 customers).

## Limits
- Moderate cluster structure; a different k gives different segments.
- Medians of different columns need not describe a single real customer.
- Lapsed customers (over 180 days) are included here but excluded from the health score.
- k = 3 (coarse view): core high-value 38% of customers / 87% of revenue, new lighter buyers 30% / 7%, lapsed mostly single-order 32% / 5%.
