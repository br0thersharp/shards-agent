const express = require('express');
const fs = require('fs');
const path = require('path');
const https = require('https');

const app = express();
const PORT = 3000;

// Paths inside the container
const STATE_DIR = process.env.OPENCLAW_STATE_DIR || '/data/openclaw-state';
const CONFIG_DIR = process.env.SHARDS_CONFIG_DIR || '/data/shards-config';

const STRATEGY_NOTES = path.join(STATE_DIR, 'strategy', 'notes.md');
const STRATEGY_MATCHUPS = path.join(STATE_DIR, 'strategy', 'matchups.md');
const STRATEGY_COMPACTED = path.join(STATE_DIR, 'strategy', 'strategy.md');
const GATEWAY_LOG = path.join(STATE_DIR, 'logs', 'gateway.log');
const COMMENTARY_LOG = path.join(STATE_DIR, 'commentary.jsonl');
const COACH_LOG = path.join(STATE_DIR, 'coach-messages.jsonl');
const SESSION_LOG = path.join(STATE_DIR, 'sessions.jsonl');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

// Shards API base
const API_BASE = 'https://api.play-shards.com';

// Cache for API credentials
let credentials = null;

function loadCredentials() {
  try {
    const raw = fs.readFileSync(CONFIG_FILE, 'utf8');
    credentials = JSON.parse(raw);
    return credentials;
  } catch (e) {
    console.error('Failed to load shards config:', e.message);
    return null;
  }
}

// Generic shards API request
function shardsApi(endpoint) {
  return new Promise((resolve, reject) => {
    if (!credentials) loadCredentials();
    if (!credentials) return reject(new Error('No credentials'));

    const url = new URL(endpoint, API_BASE);
    const options = {
      hostname: url.hostname,
      path: url.pathname + url.search,
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${credentials.access_token}`,
        'X-Api-Key': credentials.api_key,
        'Accept': 'application/json'
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve({ raw: data });
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(10000, () => { req.destroy(); reject(new Error('timeout')); });
    req.end();
  });
}

const DEBRIEF_RESPONSE = path.join(STATE_DIR, 'debrief-response.txt');
const PAUSE_FILE = path.join(STATE_DIR, 'paused');

app.use(express.json());

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

// API: Agent status — elo, games, active game, queue
app.get('/api/status', async (req, res) => {
  try {
    const [profile, queueStatus, activeGameRes] = await Promise.all([
      shardsApi('/agents/me').catch(() => null),
      shardsApi('/queue/status').catch(() => null),
      shardsApi('/agents/me/active-game').catch(() => null)
    ]);

    const activeGame = activeGameRes?.game || null;
    let gameState = null;
    if (activeGame) {
      gameState = await shardsApi(`/games/${activeGame.game_id}`).catch(() => null);
    }

    let state = 'idle';
    if (queueStatus?.in_queue) state = 'queue';
    else if (activeGame) state = 'combat';

    const gamesPlayed = profile?.gamesPlayed ?? 0;
    const wins = profile?.gamesWon ?? 0;

    res.json({
      state,
      elo: profile?.eloRating ?? '?',
      wins,
      losses: gamesPlayed - wins,
      gamesPlayed,
      flux: profile?.fluxBalance ?? 0,
      credits: profile?.creditsBalance ?? 0,
      rank: profile?.rank ?? null,
      name: profile?.name ?? 'Agent',
      activeGame: activeGame ? {
        id: activeGame.game_id,
        opponent: activeGame.opponent_name ?? '?',
        opponentFaction: '?',
        turn: gameState?.state?.t ?? gameState?.turn ?? '?',
        myHp: gameState?.state?.me?.hp ?? '?',
        opponentHp: gameState?.state?.op?.hp ?? '?'
      } : null
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// API: Activity feed — recent match results + game comments
app.get('/api/feed', async (req, res) => {
  try {
    const [matches, activeGameRes] = await Promise.all([
      shardsApi('/agents/me/games?limit=10').catch(() => null),
      shardsApi('/agents/me/active-game').catch(() => null)
    ]);

    const feed = [];

    // Get comments from active game
    const activeGame = activeGameRes?.game;
    if (activeGame) {
      try {
        const gameData = await shardsApi(`/games/${activeGame.game_id}`);
        if (gameData?.comments) {
          for (const c of gameData.comments) {
            feed.push({
              type: 'taunt',
              text: c.text || c.comment,
              author: c.agent_name || c.author || 'Agent',
              time: c.created_at || c.timestamp
            });
          }
        }
        if (gameData?.log) {
          const recentLog = gameData.log.slice(-10);
          for (const entry of recentLog) {
            if (entry.type === 'play_card' || entry.type === 'attack') {
              feed.push({
                type: 'action',
                text: entry.description || `${entry.type}: ${entry.card_name || entry.target || ''}`,
                time: entry.timestamp
              });
            }
          }
        }
      } catch {}
    }

    // Add match results
    const gamesList = matches?.data || [];
    for (const m of gamesList.filter(g => g.status === 'completed').slice(0, 5)) {
      feed.push({
        type: 'result',
        text: `Match ${m.you_won ? 'WIN' : 'LOSS'} vs ${m.opponent_name || '?'} (${m.you_won ? '+' : ''}${m.elo_change || 0} Elo)`,
        time: m.ended_at
      });
      // Get comments from completed games
      try {
        const gd = await shardsApi(`/games/${m.game_id}`);
        if (gd?.comments) {
          for (const c of gd.comments) {
            feed.push({
              type: 'taunt',
              text: c.text || c.comment,
              author: c.agent_name || c.author || '?',
              time: c.created_at || c.timestamp
            });
          }
        }
      } catch {}
    }

    // Sort by time descending
    feed.sort((a, b) => {
      if (!a.time || !b.time) return 0;
      return new Date(b.time) - new Date(a.time);
    });

    res.json({ feed: feed.slice(0, 30) });
  } catch (e) {
    res.status(500).json({ error: e.message, feed: [] });
  }
});

// API: Compacted strategy document (primary view for dashboard)
app.get('/api/notes', (req, res) => {
  try {
    const content = fs.readFileSync(STRATEGY_COMPACTED, 'utf8');
    res.json({ content });
  } catch (e) {
    // Fallback to raw notes if strategy.md doesn't exist yet
    try {
      const content = fs.readFileSync(STRATEGY_NOTES, 'utf8');
      res.json({ content });
    } catch {
      res.json({ content: '_No strategy notes yet._' });
    }
  }
});

// API: Raw BDA journal (archive)
app.get('/api/notes-raw', (req, res) => {
  try {
    const content = fs.readFileSync(STRATEGY_NOTES, 'utf8');
    res.json({ content });
  } catch (e) {
    res.json({ content: '_No raw notes yet._' });
  }
});

// API: Matchups (legacy — now part of strategy.md but kept for compatibility)
app.get('/api/matchups', (req, res) => {
  try {
    const content = fs.readFileSync(STRATEGY_MATCHUPS, 'utf8');
    res.json({ content });
  } catch (e) {
    res.json({ content: '' });
  }
});

// API: Live commentary from the agent (strip consecutive dupes)
app.get('/api/commentary', (req, res) => {
  const since = req.query.since ? new Date(req.query.since) : null;
  try {
    const content = fs.readFileSync(COMMENTARY_LOG, 'utf8');
    const lines = content.split('\n').filter(Boolean);
    const entries = [];
    let lastText = '';
    for (const line of lines.slice(-80)) {
      try {
        const entry = JSON.parse(line);
        // Skip consecutive identical messages
        if (entry.text === lastText) continue;
        lastText = entry.text;
        if (since && entry.time && new Date(entry.time) <= since) continue;
        entries.push(entry);
      } catch {}
    }
    res.json({ entries: entries.slice(-50) });
  } catch (e) {
    res.json({ entries: [] });
  }
});

// API: Send coaching feedback to the agent
app.post('/api/coach', (req, res) => {
  const { message } = req.body;
  if (!message || typeof message !== 'string') {
    return res.status(400).json({ error: 'message required' });
  }
  try {
    fs.writeFileSync(DEBRIEF_RESPONSE, message.trim(), 'utf8');
    // Also log to coach message history
    const entry = JSON.stringify({ time: new Date().toISOString(), type: 'coach', text: message.trim() });
    fs.appendFileSync(COACH_LOG, entry + '\n', 'utf8');
    debriefAcked = true;
    matchEndedAt = null;
    res.json({ ok: true, time: new Date().toISOString() });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Track last known game state for match-end detection
let lastKnownGameId = null;
let matchEndedAt = null;
let debriefAcked = false;

// API: Check if debrief is pending
// Triggers on: explicit debrief entries in commentary OR match-end detected via API
app.get('/api/debrief-status', async (req, res) => {
  const responseExists = fs.existsSync(DEBRIEF_RESPONSE);

  // Check for explicit debrief entries in commentary
  let hasDebriefEntries = false;
  try {
    const content = fs.readFileSync(COMMENTARY_LOG, 'utf8');
    const lines = content.split('\n').filter(Boolean);
    const cutoff = Date.now() - 10 * 60 * 1000;
    for (const line of lines.slice(-30)) {
      try {
        const entry = JSON.parse(line);
        if (entry.type === 'debrief') {
          const t = entry.time ? new Date(entry.time).getTime() : 0;
          if (t > cutoff || !entry.time) hasDebriefEntries = true;
        }
      } catch {}
    }
  } catch {}

  // Also detect match-end from API: if we had an active game and now we don't
  try {
    if (!credentials) loadCredentials();
    if (credentials) {
      const activeGameRes = await shardsApi('/agents/me/active-game').catch(() => null);
      const currentGame = activeGameRes?.game || null;
      const currentId = currentGame?.game_id || null;

      if (lastKnownGameId && !currentId && lastKnownGameId !== '__none__') {
        // Match just ended — trigger debrief
        if (!matchEndedAt) {
          matchEndedAt = Date.now();
          debriefAcked = false;
        }
      }

      if (currentId) {
        lastKnownGameId = currentId;
        matchEndedAt = null; // in a game, no debrief needed
        debriefAcked = false;
      } else if (!lastKnownGameId) {
        lastKnownGameId = '__none__';
      }
    }
  } catch {}

  // Debrief pending if: (explicit entries exist or match ended in last 10 min) AND not in a game
  const matchEndRecent = matchEndedAt && (Date.now() - matchEndedAt < 10 * 60 * 1000);
  const inGame = !!(lastKnownGameId && lastKnownGameId !== '__none__' && !matchEndedAt);
  const pending = !inGame && (hasDebriefEntries || matchEndRecent) && !responseExists && !debriefAcked;

  res.json({
    debriefPending: pending,
    hasDebriefEntries,
    matchEndRecent: !!matchEndRecent,
    matchEndedAt
  });
});

// API: Pause/unpause agent
app.post('/api/pause', (req, res) => {
  try {
    fs.writeFileSync(PAUSE_FILE, new Date().toISOString(), 'utf8');
    res.json({ paused: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post('/api/unpause', (req, res) => {
  try {
    if (fs.existsSync(PAUSE_FILE)) fs.unlinkSync(PAUSE_FILE);
    res.json({ paused: false });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/api/pause-status', (req, res) => {
  res.json({ paused: fs.existsSync(PAUSE_FILE) });
});

// API: Rate limit status — check marker file
const RATE_LIMIT_FILE = path.join(STATE_DIR, 'rate-limited');

app.get('/api/rate-limit-status', (req, res) => {
  try {
    if (fs.existsSync(RATE_LIMIT_FILE)) {
      const content = fs.readFileSync(RATE_LIMIT_FILE, 'utf8').trim();
      const since = content || new Date(fs.statSync(RATE_LIMIT_FILE).mtime).toISOString();
      res.json({ limited: true, since });
    } else {
      res.json({ limited: false, since: null });
    }
  } catch (e) {
    res.json({ limited: false, since: null });
  }
});

// API: Ranked/casual mode toggle
const RANKED_FILE = path.join(STATE_DIR, 'ranked');

app.post('/api/set-mode', (req, res) => {
  const { mode } = req.body;
  try {
    if (mode === 'ranked') {
      fs.writeFileSync(RANKED_FILE, new Date().toISOString(), 'utf8');
    } else {
      if (fs.existsSync(RANKED_FILE)) fs.unlinkSync(RANKED_FILE);
    }
    res.json({ mode: mode === 'ranked' ? 'ranked' : 'casual' });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/api/game-mode', (req, res) => {
  res.json({ mode: fs.existsSync(RANKED_FILE) ? 'ranked' : 'casual' });
});

// API: Coach message history
app.get('/api/coach-messages', (req, res) => {
  try {
    const content = fs.readFileSync(COACH_LOG, 'utf8');
    const lines = content.split('\n').filter(Boolean);
    const messages = [];
    for (const line of lines.slice(-20)) {
      try { messages.push(JSON.parse(line)); } catch {}
    }
    res.json({ messages });
  } catch {
    res.json({ messages: [] });
  }
});

// API: Restart agent container via Docker Engine API over unix socket
app.post('/api/restart-agent', (req, res) => {
  const http = require('http');
  const options = {
    socketPath: '/var/run/docker.sock',
    path: '/containers/oc-agent/restart?t=5',
    method: 'POST'
  };
  const dreq = http.request(options, (dres) => {
    if (dres.statusCode === 204 || dres.statusCode === 200) {
      res.json({ ok: true });
    } else {
      let body = '';
      dres.on('data', c => body += c);
      dres.on('end', () => res.status(500).json({ error: `Docker API ${dres.statusCode}: ${body}` }));
    }
  });
  dreq.on('error', (e) => res.status(500).json({ error: e.message }));
  dreq.setTimeout(30000, () => { dreq.destroy(); res.status(500).json({ error: 'timeout' }); });
  dreq.end();
});

// API: Session loop monitor
app.get('/api/sessions', (req, res) => {
  try {
    const content = fs.readFileSync(SESSION_LOG, 'utf8');
    const lines = content.split('\n').filter(Boolean);
    const entries = [];
    for (const line of lines.slice(-30)) {
      try { entries.push(JSON.parse(line)); } catch {}
    }
    // Build a summary: pair start/end events by session number
    const sessions = {};
    for (const e of entries) {
      if (!sessions[e.session]) sessions[e.session] = {};
      Object.assign(sessions[e.session], e);
    }
    const list = Object.values(sessions).sort((a, b) => (b.session || 0) - (a.session || 0)).slice(0, 10);
    const current = list.find(s => s.status === 'running') || null;
    res.json({ current, recent: list });
  } catch {
    res.json({ current: null, recent: [] });
  }
});

// API: Game scratchpad — per-turn notes from the combat agent
app.get('/api/scratchpad', async (req, res) => {
  try {
    // Find the active game ID to locate the scratchpad file
    let gameId = req.query.game_id;
    if (!gameId) {
      const activeGameRes = await shardsApi('/agents/me/active-game').catch(() => null);
      gameId = activeGameRes?.game?.game_id;
    }
    if (!gameId) {
      return res.json({ content: '', gameId: null, active: false });
    }
    const logFile = path.join(STATE_DIR, `game-log-${gameId}.txt`);
    let content = '';
    try {
      content = fs.readFileSync(logFile, 'utf8');
    } catch {}
    res.json({ content, gameId, active: true });
  } catch (e) {
    res.json({ content: '', gameId: null, active: false });
  }
});

// API: Gateway log tail
app.get('/api/log', (req, res) => {
  try {
    const content = fs.readFileSync(GATEWAY_LOG, 'utf8');
    const lines = content.split('\n').filter(Boolean).slice(-50);
    res.json({ lines });
  } catch (e) {
    res.json({ lines: [] });
  }
});

// API: Compact live match state
app.get('/api/match', async (req, res) => {
  try {
    if (!credentials) loadCredentials();
    if (!credentials) return res.json({ active: false, queuing: false });

    const activeGameRes = await shardsApi('/agents/me/active-game').catch(() => null);
    const activeGame = activeGameRes?.game || null;

    if (!activeGame) {
      // Check queue
      const queueStatus = await shardsApi('/queue/status').catch(() => null);
      const queuing = !!(queueStatus?.in_queue);

      // Parse last debrief result from commentary
      let lastResult = null;
      try {
        const content = fs.readFileSync(COMMENTARY_LOG, 'utf8');
        const lines = content.split('\n').filter(Boolean);
        for (let i = lines.length - 1; i >= 0; i--) {
          try {
            const entry = JSON.parse(lines[i]);
            if (entry.type === 'debrief') {
              lastResult = entry.text;
              break;
            }
          } catch {}
        }
      } catch {}

      // Parse last debrief cluster
      let lastDebrief = null;
      try {
        const content = fs.readFileSync(COMMENTARY_LOG, 'utf8');
        const lines = content.split('\n').filter(Boolean);
        const cluster = [];
        for (let i = lines.length - 1; i >= 0; i--) {
          try {
            const entry = JSON.parse(lines[i]);
            if (entry.type === 'debrief') {
              cluster.unshift(entry.text);
            } else if (cluster.length > 0) {
              break; // End of cluster
            }
          } catch {}
        }
        if (cluster.length > 0) lastDebrief = cluster;
      } catch {}

      return res.json({ active: false, queuing, lastResult, lastDebrief });
    }

    // Fetch full game state
    const gameState = await shardsApi(`/games/${activeGame.game_id}`).catch(() => null);
    if (!gameState || !gameState.state) {
      return res.json({ active: true, gameId: activeGame.game_id, opponent: activeGame.opponent_name || '?', partial: true });
    }

    const s = gameState.state;
    const me = s.me || {};
    const op = s.op || {};

    // Build creature lists — compact API uses .b.c with .p/.d/.t/.fd
    function mapCreatures(side) {
      // Compact: side.b.c (array of {p, d, t, fd, name/id, ...})
      const list = side.b?.c || side.creatures || side.board;
      if (!Array.isArray(list)) return [];
      return list.map(c => ({
        name: c.name || c.card_name || c.n || c.id || '?',
        power: c.p ?? c.power ?? c.attack ?? '?',
        defense: c.d ?? c.defense ?? c.health ?? c.hp ?? '?',
        tapped: !!(c.t || c.tapped),
        faceDown: !!(c.fd || c.faceDown),
        keywords: c.kw || c.keywords || []
      }));
    }

    // Extract energy — compact: en = [curr, max]
    function getEnergy(side) {
      if (Array.isArray(side.en)) return { curr: side.en[0], max: side.en[1] };
      if (side.en != null && !Array.isArray(side.en)) return { curr: side.en, max: side.en };
      return { curr: side.energy ?? '?', max: side.maxEnergy ?? side.max_energy ?? '?' };
    }

    // Extract hand size — compact: h (array for us, number for opp)
    function getHandSize(side) {
      if (side.h != null) return Array.isArray(side.h) ? side.h.length : side.h;
      if (side.handSize != null) return side.handSize;
      if (Array.isArray(side.hand)) return side.hand.length;
      return '?';
    }

    const meEnergy = getEnergy(me);
    const opEnergy = getEnergy(op);

    // Count timeouts from game log/events
    let timeouts = { me: 0, op: 0 };
    try {
      const log = gameState.log || gameState.events || [];
      for (const entry of log) {
        if (entry.type === 'TIMED_OUT' || entry.type === 'timeout' || entry.type === 'timed_out') {
          // Determine which player timed out
          if (entry.player === 'me' || entry.side === 'me' || entry.agent_id === activeGame.agent_id) {
            timeouts.me++;
          } else {
            timeouts.op++;
          }
        }
      }
    } catch {}

    // Fallback: count commentary "fallback pass" entries as HHR timeouts
    if (timeouts.me === 0 && timeouts.op === 0) {
      try {
        const content = fs.readFileSync(COMMENTARY_LOG, 'utf8');
        const lines = content.split('\n').filter(Boolean);
        const gameStart = gameState.started_at || gameState.created_at;
        for (const line of lines.slice(-50)) {
          try {
            const entry = JSON.parse(line);
            if (gameStart && entry.time && new Date(entry.time) < new Date(gameStart)) continue;
            if (entry.text && entry.text.includes('fallback pass after DB')) {
              timeouts.me++;
            }
          } catch {}
        }
      } catch {}
    }

    res.json({
      active: true,
      gameId: activeGame.game_id,
      opponent: activeGame.opponent_name || '?',
      turn: s.t ?? s.turn ?? gameState.turn ?? '?',
      phase: s.ph || s.phase || '?',
      me: {
        hp: me.hp ?? '?',
        energy: meEnergy.curr,
        maxEnergy: meEnergy.max,
        handSize: getHandSize(me),
        deckSize: me.dk ?? me.deckSize ?? me.deck_size ?? '?',
        graveyardSize: me.ds ?? me.graveyardSize ?? me.graveyard_size ?? 0,
        creatures: mapCreatures(me)
      },
      op: {
        hp: op.hp ?? '?',
        energy: opEnergy.curr,
        maxEnergy: opEnergy.max,
        handSize: getHandSize(op),
        deckSize: op.dk ?? op.deckSize ?? op.deck_size ?? '?',
        creatures: mapCreatures(op)
      },
      canAct: s.ca ?? s.canAct ?? s.can_act ?? null,
      waitingFor: s.waitingFor ?? s.waiting_for ?? null,
      timeouts
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// API: Campaign progress from sessions.jsonl + commentary debrief entries
app.get('/api/campaign', (req, res) => {
  try {
    // Read sessions.jsonl for games_completed and target
    let gamesCompleted = 0;
    let target = 10;
    try {
      const content = fs.readFileSync(SESSION_LOG, 'utf8');
      const lines = content.split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          const entry = JSON.parse(line);
          if (entry.games_completed !== undefined) gamesCompleted = Math.max(gamesCompleted, entry.games_completed);
          if (entry.target !== undefined) target = entry.target;
        } catch {}
      }
    } catch {}

    // Tally W/L from debrief commentary entries
    let wins = 0, losses = 0;
    try {
      const content = fs.readFileSync(COMMENTARY_LOG, 'utf8');
      const lines = content.split('\n').filter(Boolean);
      const seen = new Set();
      for (const line of lines) {
        try {
          const entry = JSON.parse(line);
          if (entry.type !== 'debrief') continue;
          const text = entry.text || '';
          // Only count the first debrief entry per cluster (the result line)
          // Result lines typically start with "WIN" or "LOSS"
          if (/^WIN\b/i.test(text) || /\bWIN\b/.test(text.substring(0, 30))) {
            const key = entry.time + ':win';
            if (!seen.has(key)) { wins++; seen.add(key); }
          } else if (/^LOSS\b/i.test(text) || /\bLOSS\b/.test(text.substring(0, 30))) {
            const key = entry.time + ':loss';
            if (!seen.has(key)) { losses++; seen.add(key); }
          }
        } catch {}
      }
    } catch {}

    res.json({ gamesCompleted, target, wins, losses });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Chibi Dashboard running on http://0.0.0.0:${PORT}`);
  loadCredentials();
});
