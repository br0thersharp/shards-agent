const express = require('express');
const fs = require('fs');
const path = require('path');
const https = require('https');

const app = express();
const PORT = 3000;

// Paths inside the container
const STATE_DIR = process.env.OPENCLAW_STATE_DIR || '/data/openclaw-state';
const CONFIG_DIR = process.env.SHARDS_CONFIG_DIR || '/data/shards-config';

const STRATEGY_COMPACTED = path.join(STATE_DIR, 'strategy', 'strategy.md');
const GATEWAY_LOG = path.join(STATE_DIR, 'logs', 'gateway.log');
const SESSION_LOG = path.join(STATE_DIR, 'sessions.jsonl');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

// New state files
const AGENT_STATE_FILE = path.join(STATE_DIR, 'agent-state');
const QUEUE_MODE_FILE = path.join(STATE_DIR, 'queue-mode');
const RATE_LIMIT_FILE = path.join(STATE_DIR, 'rate-limited');

// Coach chat (per-game, wiped on game end)
const COACH_MSG_FILE = path.join(STATE_DIR, 'coach-msg.txt');
const COACH_REPLY_FILE = path.join(STATE_DIR, 'coach-reply.txt');
const COACH_HISTORY_FILE = path.join(STATE_DIR, 'coach-history.jsonl');

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

app.use(express.json());

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

// ============================================================
// API: Agent status — elo, games, active game, queue
// ============================================================
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

    // Read agent state and queue mode
    let agentState = 'paused';
    try { agentState = fs.readFileSync(AGENT_STATE_FILE, 'utf8').trim(); } catch {}
    let queueMode = 'casual';
    try { queueMode = fs.readFileSync(QUEUE_MODE_FILE, 'utf8').trim(); } catch {}

    res.json({
      state,
      agentState,
      queueMode,
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
        turn: gameState?.state?.t ?? gameState?.turn ?? '?',
        myHp: gameState?.state?.me?.hp ?? '?',
        opponentHp: gameState?.state?.op?.hp ?? '?'
      } : null
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ============================================================
// API: Activity feed — recent match results + game comments
// ============================================================
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

    feed.sort((a, b) => {
      if (!a.time || !b.time) return 0;
      return new Date(b.time) - new Date(a.time);
    });

    res.json({ feed: feed.slice(0, 30) });
  } catch (e) {
    res.status(500).json({ error: e.message, feed: [] });
  }
});

// ============================================================
// API: Strategy document
// ============================================================
app.get('/api/notes', (req, res) => {
  try {
    const content = fs.readFileSync(STRATEGY_COMPACTED, 'utf8');
    res.json({ content });
  } catch {
    res.json({ content: '_No strategy notes yet._' });
  }
});

// ============================================================
// API: Agent state control (replaces pause/unpause + ranked/casual)
// ============================================================
app.get('/api/agent-state', (req, res) => {
  let agentState = 'paused';
  try { agentState = fs.readFileSync(AGENT_STATE_FILE, 'utf8').trim(); } catch {}
  let queueMode = 'casual';
  try { queueMode = fs.readFileSync(QUEUE_MODE_FILE, 'utf8').trim(); } catch {}
  res.json({ agentState, queueMode });
});

app.post('/api/agent-state', (req, res) => {
  const { agentState } = req.body;
  const valid = ['paused', 'campaign', 'challengers', 'single'];
  if (!valid.includes(agentState)) {
    return res.status(400).json({ error: `Invalid state. Must be one of: ${valid.join(', ')}` });
  }
  try {
    fs.writeFileSync(AGENT_STATE_FILE, agentState, 'utf8');
    res.json({ agentState });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post('/api/queue-mode', (req, res) => {
  const { mode } = req.body;
  if (mode !== 'casual' && mode !== 'ranked') {
    return res.status(400).json({ error: 'Must be casual or ranked' });
  }
  try {
    fs.writeFileSync(QUEUE_MODE_FILE, mode, 'utf8');
    res.json({ mode });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ============================================================
// API: Coach chat (per-game, rides the turn cycle)
// ============================================================
app.post('/api/coach', (req, res) => {
  const { message } = req.body;
  if (!message || typeof message !== 'string') {
    return res.status(400).json({ error: 'message required' });
  }
  try {
    // Write message for the agent to pick up on its next turn
    fs.writeFileSync(COACH_MSG_FILE, message.trim(), 'utf8');
    // Append to per-game history
    const entry = JSON.stringify({ time: new Date().toISOString(), from: 'coach', text: message.trim() });
    fs.appendFileSync(COACH_HISTORY_FILE, entry + '\n', 'utf8');
    res.json({ ok: true, time: new Date().toISOString() });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/api/coach', (req, res) => {
  // Get reply from agent + conversation history
  let reply = null;
  try { reply = fs.readFileSync(COACH_REPLY_FILE, 'utf8').trim(); } catch {}
  let history = [];
  try {
    const content = fs.readFileSync(COACH_HISTORY_FILE, 'utf8');
    const lines = content.split('\n').filter(Boolean);
    for (const line of lines.slice(-30)) {
      try { history.push(JSON.parse(line)); } catch {}
    }
  } catch {}
  res.json({ reply, history });
});

// ============================================================
// API: Rate limit status
// ============================================================
app.get('/api/rate-limit-status', (req, res) => {
  try {
    if (fs.existsSync(RATE_LIMIT_FILE)) {
      const content = fs.readFileSync(RATE_LIMIT_FILE, 'utf8').trim();
      const since = content || new Date(fs.statSync(RATE_LIMIT_FILE).mtime).toISOString();
      res.json({ limited: true, since });
    } else {
      res.json({ limited: false, since: null });
    }
  } catch {
    res.json({ limited: false, since: null });
  }
});

// ============================================================
// API: Restart agent container via Docker Engine API
// ============================================================
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

// ============================================================
// API: Session loop monitor
// ============================================================
app.get('/api/sessions', (req, res) => {
  try {
    const content = fs.readFileSync(SESSION_LOG, 'utf8');
    const lines = content.split('\n').filter(Boolean);
    const entries = [];
    for (const line of lines.slice(-30)) {
      try { entries.push(JSON.parse(line)); } catch {}
    }
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

// ============================================================
// API: Gateway log tail
// ============================================================
app.get('/api/log', (req, res) => {
  try {
    const content = fs.readFileSync(GATEWAY_LOG, 'utf8');
    const lines = content.split('\n').filter(Boolean).slice(-50);
    res.json({ lines });
  } catch {
    res.json({ lines: [] });
  }
});

// ============================================================
// API: Compact live match state (all data from shards API, zero agent tokens)
// ============================================================
app.get('/api/match', async (req, res) => {
  try {
    if (!credentials) loadCredentials();
    if (!credentials) return res.json({ active: false, queuing: false });

    const activeGameRes = await shardsApi('/agents/me/active-game').catch(() => null);
    const activeGame = activeGameRes?.game || null;

    if (!activeGame) {
      const queueStatus = await shardsApi('/queue/status').catch(() => null);
      const queuing = !!(queueStatus?.in_queue);
      return res.json({ active: false, queuing });
    }

    const gameState = await shardsApi(`/games/${activeGame.game_id}`).catch(() => null);
    if (!gameState || !gameState.state) {
      return res.json({ active: true, gameId: activeGame.game_id, opponent: activeGame.opponent_name || '?', partial: true });
    }

    const s = gameState.state;
    const me = s.me || {};
    const op = s.op || {};

    function mapCreatures(side) {
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

    function getEnergy(side) {
      if (Array.isArray(side.en)) return { curr: side.en[0], max: side.en[1] };
      if (side.en != null && !Array.isArray(side.en)) return { curr: side.en, max: side.en };
      return { curr: side.energy ?? '?', max: side.maxEnergy ?? side.max_energy ?? '?' };
    }

    function getHandSize(side) {
      if (side.h != null) return Array.isArray(side.h) ? side.h.length : side.h;
      if (side.handSize != null) return side.handSize;
      if (Array.isArray(side.hand)) return side.hand.length;
      return '?';
    }

    const meEnergy = getEnergy(me);
    const opEnergy = getEnergy(op);

    // Count timeouts from game log
    let timeouts = { me: 0, op: 0 };
    try {
      const log = gameState.log || gameState.events || [];
      for (const entry of log) {
        if (entry.type === 'TIMED_OUT' || entry.type === 'timeout' || entry.type === 'timed_out') {
          if (entry.player === 'me' || entry.side === 'me' || entry.agent_id === activeGame.agent_id) {
            timeouts.me++;
          } else {
            timeouts.op++;
          }
        }
      }
    } catch {}

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

// ============================================================
// API: Campaign progress from sessions.jsonl
// ============================================================
app.get('/api/campaign', async (req, res) => {
  try {
    let gamesCompleted = 0;
    let target = 0;
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

    // Get W/L from API instead of commentary
    let wins = 0, losses = 0;
    try {
      const profile = await shardsApi('/agents/me').catch(() => null);
      wins = profile?.gamesWon ?? 0;
      losses = (profile?.gamesPlayed ?? 0) - wins;
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
