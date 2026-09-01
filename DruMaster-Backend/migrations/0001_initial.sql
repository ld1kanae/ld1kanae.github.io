PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS players (
  player_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plays (
  play_id TEXT PRIMARY KEY,
  player_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  song_id TEXT NOT NULL,
  chart_id TEXT NOT NULL,
  ranking_version TEXT NOT NULL,
  chart_version TEXT NOT NULL,
  game_version TEXT NOT NULL,
  score INTEGER NOT NULL CHECK (score >= 0 AND score <= 1000000),
  perfect INTEGER NOT NULL CHECK (perfect >= 0),
  great INTEGER NOT NULL CHECK (great >= 0),
  good INTEGER NOT NULL CHECK (good >= 0),
  miss INTEGER NOT NULL CHECK (miss >= 0),
  note_count INTEGER NOT NULL CHECK (note_count >= 0),
  max_combo INTEGER,
  play_mode TEXT NOT NULL,
  played_at_client TEXT NOT NULL,
  received_at_server TEXT NOT NULL,
  FOREIGN KEY (player_id) REFERENCES players(player_id)
);

CREATE INDEX IF NOT EXISTS idx_plays_board
  ON plays(song_id, chart_id, ranking_version, score DESC, received_at_server ASC);

CREATE INDEX IF NOT EXISTS idx_plays_player_board
  ON plays(player_id, song_id, chart_id, ranking_version, score DESC);

CREATE INDEX IF NOT EXISTS idx_plays_received
  ON plays(received_at_server DESC);
