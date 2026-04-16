# Structure Rules

- Keep business logic in `app/core/**`
- Keep UI orchestration in `app/ui/**`
- Keep runtime/user assets in `user_data/**`
- Keep project docs in `data/docs/**`
- Keep assistant rules in `data/rules/**`
- Keep AI as a later layer, not the center of the app right now

## Versioning rule
AI changes must go through candidate versions, diff review, and explicit accept.
