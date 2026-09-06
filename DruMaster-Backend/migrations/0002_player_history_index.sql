CREATE INDEX IF NOT EXISTS idx_plays_player_history
  ON plays(player_id, received_at_server ASC, play_id ASC);
