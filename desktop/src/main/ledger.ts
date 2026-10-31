/**
 * Local audit ledger — better-sqlite3 in WAL mode.
 *
 * Every generation, approval, credential issuance, and revocation is
 * appended here with an ISO-8601 timestamp. The ledger is the local
 * compliance record; exports feed the Markdown/JSON/PDF audit reports.
 *
 * Schema changes must go through `MIGRATIONS` with a bumped
 * `SCHEMA_VERSION` — never ad-hoc ALTERs at call sites.
 */

import Database from 'better-sqlite3'
import type { AuditEvent, AuditKind } from '../shared/ipc-contract'

export const SCHEMA_VERSION = 1

const MIGRATIONS: string[] = [
  `CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}'
  );
  CREATE INDEX IF NOT EXISTS idx_audit_events_ts ON audit_events (ts DESC);
  CREATE INDEX IF NOT EXISTS idx_audit_events_kind ON audit_events (kind);`,
]

export class Ledger {
  private db: Database.Database

  constructor(dbPath: string) {
    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('foreign_keys = ON')
    this.migrate()
  }

  private migrate(): void {
    this.db.exec('CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    const row = this.db
      .prepare("SELECT value FROM schema_meta WHERE key = 'version'")
      .get() as { value: string } | undefined
    const current = row ? Number(row.value) : 0
    const migrateTx = this.db.transaction((from: number) => {
      for (let v = from; v < SCHEMA_VERSION; v += 1) {
        this.db.exec(MIGRATIONS[v])
      }
      this.db
        .prepare("INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)")
        .run(String(SCHEMA_VERSION))
    })
    migrateTx(current)
  }

  append(kind: AuditKind, summary: string, details: Record<string, unknown> = {}): number {
    const result = this.db
      .prepare('INSERT INTO audit_events (ts, kind, summary, details) VALUES (?, ?, ?, ?)')
      .run(new Date().toISOString(), kind, summary, JSON.stringify(details))
    const id = Number(result.lastInsertRowid)
    const event = this.recent(50).find((e) => e.id === id)
    return event?.id ?? id
  }

  recent(limit = 100): AuditEvent[] {
    return this.db
      .prepare('SELECT id, ts, kind, summary, details FROM audit_events ORDER BY id DESC LIMIT ?')
      .all(Math.min(Math.max(limit, 1), 500)) as AuditEvent[]
  }

  close(): void {
    this.db.close()
  }
}

export function eventsToMarkdown(events: AuditEvent[]): string {
  const lines = [
    '# IAM-Dynamic Audit Report',
    '',
    `Exported: ${new Date().toISOString()}`,
    `Events: ${events.length}`,
    '',
    '| ID | Timestamp | Kind | Summary |',
    '| --- | --- | --- | --- |',
  ]
  for (const e of [...events].reverse()) {
    lines.push(`| ${e.id} | ${e.ts} | ${e.kind} | ${e.summary.replace(/\|/g, '\\|')} |`)
  }
  return `${lines.join('\n')}\n`
}
