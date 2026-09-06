# DruMaster Ranking / Record Sync Specification

Updated: 2026-09-07

This document is the source-of-truth contract for score persistence and cross-client synchronization across Web, Windows and Android.

## Core invariants

1. Every client owns a durable local play history.
   - Web: IndexedDB in the browser origin.
   - Windows: IndexedDB in the packaged WebView origin.
   - Android: IndexedDB in the packaged WebView origin.
   - All three use the same shared implementation: `DruMaster/js/ranking-sync.js`.

2. A play result is committed locally before any network request is required.
   - RESULT becomes visible.
   - The complete play record is written to local IndexedDB `drumaster-ranking / plays` with `syncStatus = pending`.
   - Local BEST / RECORD RANKING is rebuilt from that local database.
   - Only after the local commit does cloud synchronization begin.

3. Cloud failure must never remove, hide or invalidate a local result.
   - Offline / HTTP 5xx / quota errors leave the local play intact.
   - Failed uploads remain `pending` for the next synchronization opportunity.
   - RECORD RANKING always reads local history, not the network.

4. The cloud is a merge layer, not the primary UI datastore.
   - Every play has a unique `playId`.
   - POST `/v1/plays` is idempotent by `playId`.
   - Records from Web / Windows / Android accumulate in the same cloud history for the linked player identities.

5. Cloud-to-local synchronization is differential.
   - The backend provides an opaque cursor on `/v1/players/:playerId/plays?cursor=...`.
   - The cursor is based on the server receipt ordering `(received_at_server, play_id)` and is supported by the player-history index.
   - A client asks only for rows after its last saved cursor.
   - Responses are paginated; the client advances its cursor only after receiving a page.
   - Existing `playId` rows are merged/updated locally; new rows are inserted.

6. Synchronization is event-driven, not timer-driven.
   Normal automatic sync triggers are only:
   - once during application/page startup;
   - once after a rankable RESULT has been committed locally.

   There is no 30-second / 5-minute retry timer, no 15-minute history throttle, and no focus/HOME polling sync.

7. No ranking network request is allowed to compete with active gameplay.
   - `offline-playback.js` blocks network APIs while `running === true`.
   - Because synchronization has no timer/focus trigger, ranking requests are not intentionally started during gameplay.
   - RESULT synchronization occurs after gameplay has ended.

## Local database

Primary datastore:

- Database: `drumaster-ranking`
- Store: `plays`
- Key: `playId`
- Important indexes: `syncStatus`, `playedAtClient`, `songId`, `playerId`

A play contains at least:

- `playId`
- `playerId`
- `displayName`
- `songId`
- `chartId`
- `rankingVersion`
- `chartVersion`
- `gameVersion`
- `score`
- `perfect`, `great`, `good`, `miss`, `noteCount`
- `maxCombo`
- `playMode`
- `playedAtClient`
- `createdAtLocal`
- `syncStatus` (`pending` or `synced`)
- retry/error metadata

The temporary second database `drumaster-local-history` is no longer an active datastore. On first launch of the unified client, records found there are merged once into `drumaster-ranking`; the old database is left untouched as a safety backup but is not read by normal ranking UI afterwards.

## Startup flow

1. Open/upgrade local IndexedDB.
2. One-time merge of any records from the temporary detached local-history database.
3. Build local merged state and BEST data.
4. Send every local `pending` play to the cloud.
5. For the current player ID and linked historical IDs, request cloud rows after each saved cursor.
6. Merge received rows into local IndexedDB.
7. Rebuild local state / RECORD RANKING.
8. Save the returned cursor for the next startup/result sync.

## RESULT flow

1. Gameplay finishes.
2. RESULT values are finalized.
3. Create one new `playId`.
4. Write the play to local IndexedDB as `pending`.
5. Rebuild local BEST / RECORD RANKING immediately.
6. Push pending rows to cloud.
7. Pull cloud deltas since the previous cursor.
8. Merge the deltas locally.
9. Rebuild local state again.

AUTO PLAY and NO SCORE results are not inserted into ranked play history.

## Device identity linking

The user can enter another client’s Player ID / sync code.

- The entered ID becomes the canonical ID for future plays on that client.
- Previous IDs are retained as linked aliases so their existing cloud history is still pulled.
- Linking does not clone old plays into duplicate new `playId` records.
- Pending rows keep their original identity and can still be uploaded idempotently.

## Compatibility and migration

- `localStorage.drumusterBest` remains only as a compatibility mirror for old UI paths; the durable play database is authoritative.
- Legacy BEST migration may add synthetic legacy records, but normal new plays always use full local records.
- The old full-history endpoint behavior is retained when the `cursor` query parameter is absent so already-installed older clients do not immediately break.
- New clients always use cursor mode.

## Failure behavior

If upload fails:
- local result remains visible and durable;
- `syncStatus` remains `pending`;
- it is retried at the next startup or next RESULT sync.

If delta download fails:
- already-local records remain available;
- the cursor is not advanced past data that was not received;
- the next startup or RESULT tries the same missing delta again.

If the app is closed after a local commit but before cloud upload:
- the pending local record is sent on the next startup.

## Performance requirements

- No periodic ranking timer.
- No full 5,000-row history scan during routine synchronization.
- Routine synchronization transfers only rows added since the saved cursor.
- No ranking network activity during active performance.
- RECORD RANKING reads local IndexedDB only.
