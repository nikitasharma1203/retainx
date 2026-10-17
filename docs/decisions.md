# Decisions

| Decision | Choice | Why |
|---|---|---|
| Core dataset | UCI Online Retail II only | It has customer IDs and about two years of repeat purchases. The other datasets share no keys with it. |
| Walmart data | Separate side module for demand only, later | No customers, so it cannot support customer models |
| Cancellations | Excluded, not netted against the original order | Simple and visible. Netting is better for revenue accuracy but more work. Revisit if returns matter. |
| Missing customer ID | Excluded from customer models | Cannot be attributed to a person |
| Non-product stock codes | Keep codes starting with five digits | Drops POST, D, M, BANK CHARGES etc. Check the profile output for codes this wrongly removes or keeps. |
| `dim_customer` | No last_order or lifetime totals | Those would leak the future into features. Use `customer_rfm` or `src/features.py` at a cutoff. |
| Churn definition | Active in last 180 days, no order in next 90 | Needs a window. Change in `src/config.py`. |
| Propensity definition | All known customers, order in next 30 days | Different from churn on purpose: wider base, shorter horizon |
| Splits | Time-based only, label window must end before the test cutoff | Random splits leak. `train_eval` raises if windows overlap. |
| Ranking signal | Repeat-purchase rate | The dataset has no ratings. State this limit when presenting. |
| MCP | Narrow read-only tools, no raw SQL | Agent cannot pick the wrong redundant table |

## Said no to (for now)
- Real-time streaming
- UI polish
- Deep-learning models before a simple baseline is beaten
- Pricing and demand before phase 1 is solid
