# Harbor newsletter data contract

Newsletter Intelligence consumes Harbor's normalized newsletter model rather
than provider response objects. Provider adapters live under
`harbor/connectors/` and translate authenticated source data at the boundary.

## Metric semantics

Every metric carries one explicit state:

- `available`: the provider returned a numeric value. Zero is a valid value.
- `no_data`: the provider supports the metric but returned no value.
- `not_supported`: the provider does not expose the metric Harbor requested.
- `insufficient_history`: Harbor cannot yet calculate a historical comparison.

Only an `available` metric may contain a numeric value. This prevents missing
provider fields from silently becoming zero in analysis, persisted runs, email,
or the ChatGPT interface.

## Normalized objects

- `NewsletterDataset` identifies the requested date window, capture time,
  capabilities, publications, warnings, and explicit mock state.
- `NewsletterPublication` identifies its provider and connection, contains
  audience and aggregate engagement metrics, and owns issues, segments, growth
  attribution, and safe provider metadata.
- `NewsletterIssue` contains title, subject line, send date, audience/tags, and
  normalized delivery, engagement, unsubscribe, and web metrics.

Provider identifiers remain source metadata. Workers select publications using
tenant configuration or explicit scoped inputs; they never embed customer IDs.

## Connector contract

Each connector declares a provider, source type, and capabilities, then
implements resource discovery, access verification, and normalized sync. The
registry resolves `(source_type, provider)` at runtime. Adding a newsletter
provider therefore requires an adapter, not provider branches inside Newsletter
Intelligence.

The Beehiiv adapter preserves the existing Sprite Connector credential path and
legacy single-publication configuration while persisting the normalized dataset
with each run.

The Kit adapter targets API v4 and treats the authenticated Kit account as the
publication resource exposed by that API. Completed broadcast stats map to
issues; account subscriber counts, date-bounded growth, and tags map to the
publication. Metrics Kit does not return—such as delivered count, unique opens,
and spam reports—are explicitly `not_supported`, never zero.

## Time windows

Newsletter requests accept `today`, `yesterday`, `last_7_days`, `week`,
`month`, `last_30_days`, `quarter`, `last_90_days`, `six_months`, `ytd`,
`previous_year`, or an inclusive custom date range. Harbor resolves customer
dates in the tenant timezone and stores explicit UTC start/end timestamps. The
end timestamp is exclusive. Bounded runs also fetch a prior equal-duration
window; YTD compares with the same elapsed period in the prior year.

## Publication and portfolio selection

The same worker accepts one or more `connection_ids` and `publication_ids`.
`view=publication` requires exactly one normalized publication. `view=portfolio`
combines every selected provider without provider-specific analysis code. Total
audience is only calculated when every selected publication returned an
available subscriber count; engagement is recipient-weighted across comparable
issues. Provider failures fail the portfolio run visibly rather than silently
returning a partial portfolio.
