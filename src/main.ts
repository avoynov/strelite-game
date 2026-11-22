import { Application } from 'pixi.js';
import './style.css';
import { getLang, onLangChange, t } from './i18n';
import { BoardRenderer, type Armed, type Selection } from './render/boardRenderer';
import { PALETTE } from './render/palette';
import { PortraitArt } from './render/portraitArt';
import { TowerArt } from './render/towers/spriteTowerView';
import { ENEMIES, TICK, TOWERS } from './sim/content';
import { FixedStep } from './sim/fixedStep';
import { Game } from './sim/game';
import { buildArcMap, buildPathMap, type Mode } from './sim/maps';
import { levelArcMap, levelMap } from './sim/levels';
import { readAimPrefs } from './aimPrefs';
import { LevelSelect } from './ui/levels';
import { attachGestures } from './ui/gestures';
import { Arsenal } from './ui/arsenal';
import { Lab, itemName } from './ui/lab';
import { ResearchStore } from './researchStore';
import { BaseStore } from './baseStore';
import { ProgressStore } from './progressStore';
import { starsFor, type OrderEvent } from './sim/progress';
import { battleTakings, researchItem } from './sim/research';
import { BASE_MAP, baseTakings, BUILDING_KINDS, buildingHp, jobPrice, liberate, occupy, treasuryLoss, type BuildingKind } from './sim/base';
import { attackStrength, defenceStrength } from './sim/strength';
import { Hud, rankName, type BaseHud, type BaseResult, type MissionResult } from './ui/hud';
import { GameAudio } from './audio/audio';
import type { SoundName } from './audio/synth';
import { installWay, onInstallChange, promptInstall } from './pwa/install';
import { AUTO_STEPS, FrameWatch, qualityFor, readChoice, saveAutoStep, saveChoice, startStep, type QualityChoice } from './perf';
import { PauseMenu } from './ui/pauseMenu';
import { CHEAT_GOLD, readCheats, writeCheats } from './cheats';
import type { EnemyId, TowerId } from './sim/content';

const ART_URL = `${import.meta.env.BASE_URL}art`;
/** The running path or arc battle, so closing the game does not lose it. */
const BATTLE_KEY = 'strelite.battle';

/** Each gun's report. The flamethrower is a held loop instead; the railgun has its own event. */
const SHOT_SOUND: Partial<Record<TowerId, SoundName>> = { crossbow: 'crossbow', scorpion: 'scorpion', zis3: 'zis3', howitzer: 'howitzer', trebuchet: 'trebuchet' };
const DEATH_SOUND: Record<EnemyId, SoundName> = { infantry: 'deathSoft', moto: 'deathVehicle', drone: 'deathAir', truck: 'deathVehicle', apc: 'deathVehicle', tank: 'deathVehicle', fortress: 'deathBig' };

const MODES: readonly Mode[] = ['path', 'arc', 'siege'];
const asMode = (v: string | null): Mode | null => MODES.find((m) => m === v) ?? null;

/**
 * Where the game opens: the base (the game's hub, mode 'siege'), unless the
 * address asks for a mission (`?mode=path|arc`) or a mission was left running.
 */
function readMode(): Mode {
  return asMode(new URLSearchParams(location.search).get('mode')) ?? readBattle()?.mode ?? 'siege';
}

let mode: Mode = readMode();
/** Each mode keeps its own progress through the levels. */
const levelKey = () => (mode === 'path' ? 'strelite.level' : `strelite.level.${mode}`);
const wonKey = () => (mode === 'path' ? 'strelite.won' : `strelite.won.${mode}`);

function readNumber(key: string): number {
  try {
    return Math.max(0, Math.floor(Number(localStorage.getItem(key)) || 0));
  } catch {
    return 0;
  }
}

function saveString(key: string, v: string): void {
  try {
    localStorage.setItem(key, v);
  } catch {
    // Private mode or blocked storage: it just is not remembered.
  }
}

const saveNumber = (key: string, n: number) => saveString(key, String(n));

/** Highest map level won so far. */
const wonLevel = () => readNumber(wonKey());
/** The next mission of a kind: the first level not won yet. */
const missionLevel = (m: 'path' | 'arc') => readNumber(m === 'path' ? 'strelite.won' : 'strelite.won.arc') + 1;

/** Map level to play: `?level=N` wins, else the last one played (never past the next unwon), else 1. */
function startLevel(): number {
  const fromUrl = Number(new URLSearchParams(location.search).get('level'));
  if (fromUrl >= 1) return Math.floor(fromUrl);
  return Math.min(Math.max(1, readNumber(levelKey())), wonLevel() + 1);
}

function readBattle(): { mode: Mode; level: number; save: unknown } | null {
  try {
    const raw = JSON.parse(localStorage.getItem(BATTLE_KEY) ?? 'null') as { mode?: unknown; level?: unknown } | null;
    const m = asMode(typeof raw?.mode === 'string' ? raw.mode : null);
    const level = Number(raw?.level);
    return m && level >= 1 ? { mode: m, level: Math.floor(level), save: raw } : null;
  } catch {
    return null;
  }
}

function clearBattle(): void {
  try {
    localStorage.removeItem(BATTLE_KEY);
  } catch {
    // Nothing saved anyway.
  }
}

async function start(): Promise<void> {
  document.documentElement.lang = getLang();
  document.title = t('game.title');

  const audio = new GameAudio();
  let qualityChoice: QualityChoice = readChoice();
  let autoStep = startStep();
  let quality = qualityFor(qualityChoice, autoStep);

  const app = new Application();
  const [art, portraits] = await Promise.all([
    TowerArt.load(ART_URL),
    PortraitArt.load(ART_URL),
    app.init({
      resizeTo: window,
      background: PALETTE.background,
      antialias: quality.antialias,
      autoDensity: true,
      resolution: quality.resolution,
      // Weak phones: let the browser pick the cheaper GPU path.
      powerPreference: quality.antialias ? 'high-performance' : 'low-power',
    }),
  ]);
  art?.allowSharp(quality.sharpArt);
  app.ticker.maxFPS = quality.maxFps;
  await art?.preload();
  portraits?.preload();
  document.getElementById('board')!.appendChild(app.canvas);

  const params = new URLSearchParams(location.search);
  // `?fastresearch` runs research and building timers 600× faster, for trying things out.
  const fast = params.has('fastresearch') ? 600 : 1;
  const research = new ResearchStore(fast);
  const baseStore = new BaseStore(fast);
  /** The base spends straight from the treasury. */
  const wallet = {
    get gold() {
      return research.state.gold;
    },
    set gold(v: number) {
      research.setGold(v);
    },
  };
  /** Research follows the laboratory in the base: its level, and whether it stands. */
  const syncLab = () => {
    const l = baseStore.state.buildings.lab;
    research.setLab({ level: l.level, standing: l.hp > 0, hq: baseStore.state.buildings.hq.level });
  };
  baseStore.settle();
  syncLab();
  const progress = new ProgressStore();
  /** Highest map level won in either mission, and the highest the player may fight. */
  const highestWon = () => Math.max(missionLevel('path'), missionLevel('arc')) - 1;
  const reached = () => highestWon() + 1;
  /** Count something towards today's order; when that finishes it, pay it and say so. */
  const reportOrder = (ev: OrderEvent): number => {
    const paid = progress.report(ev, reached(), highestWon());
    if (!paid) return 0;
    research.bank(paid.gold);
    hud.showToast(t('toast.orderDone', { n: paid.gold }));
    audio.play('waveClear');
    return paid.gold;
  };
  /** A battle's takings with the full Fortress set's share on top. */
  const withBonus = (gold: number) => Math.round(gold * (1 + research.upgrades().goldBonus));
  /** Once a battle at the base is over: how it went. */
  let baseResult: BaseResult | null = null;

  const newGame = (level: number) => {
    if (mode === 'siege') {
      // The base: one fixed field; the attack number comes from the saved base.
      baseStore.settle();
      syncLab();
      return new Game(buildArcMap(BASE_MAP, 'siege'), {
        level: baseStore.state.attack,
        upgrades: research.upgrades(),
        aimPrefs: readAimPrefs(),
        base: {
          get state() {
            return baseStore.state;
          },
          wallet,
          speed: fast,
        },
      });
    }
    return new Game(mode === 'path' ? buildPathMap(levelMap(level)) : buildArcMap(levelArcMap(level), mode), { level, upgrades: research.upgrades(), aimPrefs: readAimPrefs() });
  };
  // A battle left running last time picks up where it stopped (unless a level was asked for in the address).
  const saved = params.has('level') ? null : readBattle();
  let game = newGame(saved && saved.mode === mode ? saved.level : startLevel());
  const resumed = !!saved && saved.mode === mode && game.restoreBattle(saved.save);
  if (saved && !resumed) clearBattle();

  /** Path and arc modes: keep the running battle, or forget it once over. */
  const saveBattle = () => {
    if (game.base) return;
    const save = game.saveBattle();
    if (!save) {
      clearBattle();
      return;
    }
    saveString(BATTLE_KEY, JSON.stringify(save));
  };

  /**
   * Base mode: write what stands into the saved base. Building levels, jobs and
   * the occupation are the store's: a building raised or rebuilt while the
   * battle ran keeps its new level and health, carrying the damage it took.
   */
  const saveBase = () => {
    if (!game.base) return;
    const snap = game.snapshot();
    const st = baseStore.state;
    const buildings = { ...st.buildings };
    for (const k of BUILDING_KINDS) {
      const live = snap.buildings[k];
      const saved = st.buildings[k];
      // Ruins since the battle began: the store knows best (they may have been rebuilt meanwhile).
      if (live.hp <= 0 && !game.ruined.has(k)) continue;
      if (live.hp <= 0) {
        buildings[k] = { level: saved.level, hp: 0 };
        continue;
      }
      if (saved.hp <= 0) continue;
      const from = buildingHp(k, live.level);
      const to = buildingHp(k, saved.level);
      buildings[k] = { level: saved.level, hp: Math.max(1, Math.min(to, live.hp + to - from)) };
    }
    baseStore.set({ ...st, buildings, guns: snap.guns, fences: snap.fences });
  };
  let enemyStrength = { attack: 0, hq: -1, value: 0 };
  const baseHud: BaseHud = {
    state: () => baseStore.state,
    startJob: (what) => {
      saveBase();
      const kind = jobPriceKind(what);
      const err = baseStore.startJob(what, wallet);
      if (!err) {
        syncLab();
        if (kind === 'upgrade') reportOrder({ type: 'upgrade' });
      }
      return err;
    },
    strength: () => {
      const hq = game.hq?.level ?? 0;
      if (enemyStrength.attack !== game.level || enemyStrength.hq !== hq) enemyStrength = { attack: game.level, hq, value: attackStrength(game.level, undefined, undefined, hq) };
      return { you: defenceStrength(game), enemy: enemyStrength.value };
    },
    result: () => baseResult,
    speed: fast,
    missions: () => ({ path: missionLevel('path'), arc: missionLevel('arc') }),
    startMission: (m, level) => goTo(m, level),
    openLevels: () => levels.open(),
    order: () => {
      const order = progress.order(reached());
      return { order, state: progress.state, reward: progress.reward(highestWon()).gold };
    },
    stars: () => ({ total: progress.totalStars(), medals: progress.medals }),
    provoked: () => {
      hud.showToast(t('toast.raid'));
      audio.play('waveStart');
    },
  };
  /** Gold this battle put in the treasury when it ended; null while it runs. */
  let banked: number | null = null;
  /** A finished mission: its stars and what they (and the order) paid. */
  let missionResult: MissionResult | null = null;
  const jobPriceKind = (what: BuildingKind) => jobPrice(baseStore.state, what)?.kind ?? null;
  let board = new BoardRenderer(game, art, ART_URL);
  app.stage.addChild(board.root);
  let selection: Selection | null = null;
  let armed: Armed | null = null;
  let loop = new FixedStep(TICK, (dt) => game.step(dt));

  const hud = new Hud(document.getElementById('hud')!, game, {
    getSelection: () => selection,
    anchor: () => board.anchorOf(selection),
    setSelection: (s) => (selection = s),
    getArmed: () => armed,
    setArmed: (def) => {
      armed = def;
      selection = null;
    },
    towerIcon: (def) => art?.iconCss(def, 52) ?? '',
    getSpeed: () => loop.speed,
    setSpeed: (s) => (loop.speed = s),
    restart: (level = game.level) => goTo(mode, level),
    openArsenal: () => arsenal.open(armed && armed !== 'fence' ? armed : undefined),
    openLab: () => lab.open(),
    toBase: () => goTo('siege'),
    banked: () => banked ?? 0,
    missionResult: () => missionResult,
    base: () => (game.base ? baseHud : null),
    pause: () => pause(),
    done: () => audio.play('build'),
  });

  /** Open the base, or a mission (path or arc) at a level. */
  function goTo(next: Mode, level = 1): void {
    {
      const speed = loop.speed;
      if (paused) {
        paused = false;
        loop.paused = false;
        audio.setPaused(false);
        pauseMenu.close();
      }
      saveBase();
      mode = next;
      if (next !== 'siege') saveNumber(levelKey(), level);
      board.destroy();
      clearBattle();
      game = newGame(level);
      banked = null;
      baseResult = null;
      missionResult = null;
      board = new BoardRenderer(game, art, ART_URL);
      app.stage.addChild(board.root);
      loop = new FixedStep(TICK, (dt) => game.step(dt));
      loop.speed = speed;
      selection = null;
      armed = null;
      hud.setGame(game);
      relayout();
      if (!game.base) arsenal.open(); // a mission starts with the arsenal
    }
  }

  // ---- pause ---------------------------------------------------------------

  let paused = false;
  const watch = new FrameWatch();
  const pause = () => {
    if (paused) return;
    paused = true;
    loop.paused = true;
    audio.setPaused(true);
    saveBattle();
    pauseMenu.open();
  };
  const applyQuality = () => {
    quality = qualityFor(qualityChoice, autoStep);
    art?.allowSharp(quality.sharpArt);
    app.ticker.maxFPS = quality.maxFps;
    if (app.renderer.resolution !== quality.resolution) app.renderer.resize(app.screen.width, app.screen.height, quality.resolution);
    watch.reset();
    relayout();
  };
  /** Testing switches from the pause screen: endless gold, no waiting. */
  let cheats = readCheats();
  const applyCheats = () => {
    if (cheats.gold) {
      if (game.money < CHEAT_GOLD) game.money = CHEAT_GOLD;
      if (research.state.gold < CHEAT_GOLD) research.setGold(CHEAT_GOLD);
    }
    if (cheats.instant) {
      const now = Date.now();
      research.finishNow(now);
      baseStore.finishNow(now);
      for (const tw of game.towers) if (tw.job && tw.job.endsAt > now) tw.job.endsAt = now;
    }
  };
  const pauseMenu = new PauseMenu({
    audio: () => audio.settings,
    setAudio: (s) => audio.set(s),
    quality: () => qualityChoice,
    setQuality: (q) => {
      qualityChoice = q;
      saveChoice(q);
      applyQuality();
    },
    installWay,
    install: () => void promptInstall().then(() => pauseMenu.invalidate()),
    cheats: () => cheats,
    setCheats: (c) => {
      cheats = { ...cheats, ...c };
      writeCheats(cheats);
      applyCheats();
      hud.update();
    },
    inBase: () => !!game.base,
    toBase: () => goTo('siege'),
    resume: () => {
      paused = false;
      loop.paused = false;
      audio.setPaused(false);
      watch.reset();
      hud.update();
    },
  });
  document.body.appendChild(pauseMenu.el);
  onInstallChange(() => pauseMenu.invalidate());

  let listMode: Mode = 'path';
  const levels = new LevelSelect({
    won: () => missionLevel(listMode === 'arc' ? 'arc' : 'path') - 1,
    stars: (level) => progress.starsOf(listMode === 'arc' ? 'arc' : 'path', level),
    totals: () => ({ total: progress.totalStars(), medals: progress.medals }),
    current: () => (game.mode === listMode ? game.level : 0),
    mode: () => listMode,
    // The list shows one kind of mission at a time; picking a level starts it.
    setMode: (m) => {
      listMode = m;
    },
    play: (level) => goTo(listMode, level),
    close: () => hud.update(),
  });
  document.body.appendChild(levels.el);

  /** The research screen shows each gun from the same three-quarter angle as the arsenal at rest. */
  const LAB_FRAME = 28;
  const lab = new Lab({
    state: () => research.state,
    lab: () => research.lab,
    start: (id) => research.start(id),
    speed: research.speed,
    portrait: (def, level) =>
      portraits?.has(def) ? portraits.portrait(def, level, LAB_FRAME, art?.manifest.directions ?? 32) : art?.portrait(def, level, LAB_FRAME),
    onArt: (fn) => art?.onChange(fn) ?? (() => {}),
    celebrate: () => audio.play('waveClear'),
    close: () => hud.update(),
  });
  document.body.appendChild(lab.el);
  // A finished item is announced wherever the player is; it counts from the next battle.
  let doneCount = research.state.done.length;
  let ticks = 0;
  window.setInterval(() => {
    const done = research.state.done;
    for (const id of done.slice(doneCount)) {
      const item = researchItem(id);
      if (item) hud.showToast(t('toast.researchDone', { name: itemName(item) }));
    }
    if (done.length !== doneCount) lab.invalidate();
    doneCount = done.length;
    // The base is saved every second, and its builders finish on the clock.
    saveBase();
    const before = baseStore.state;
    if (baseStore.settle()) {
      const after = baseStore.state;
      syncLab();
      lab.invalidate();
      for (const k of BUILDING_KINDS) {
        const a = after.buildings[k];
        const b = before.buildings[k];
        if (a.level !== b.level && (k === 'hq' || k === 'lab' || k === 'treasury')) hud.showToast(t('toast.jobDone', { name: t(`building.${k}`), n: a.level + 1 }));
        else if (a.hp > 0 && b.hp <= 0) hud.showToast(t('toast.built', { name: t(`building.${k}`) }));
      }
      // In peace the base is rebuilt at once with the new levels; during an attack they count from the next.
      if (game.base && game.phase === 'build' && game.wave === 0) hud.restartAt(game.level);
    }
    // A new order is sealed at local midnight.
    if (progress.roll()) hud.invalidate();
    // The running battle every few seconds, in case the app is killed without warning.
    if (++ticks % 5 === 0 && !paused) saveBattle();
  }, 1000);
  // Leaving the app pauses the battle and saves it; coming back shows the pause screen.
  const onHide = () => {
    saveBase();
    if (!paused && game.phase !== 'won' && game.phase !== 'lost' && !arsenal.isOpen && !lab.isOpen && !levels.isOpen) pause();
    else saveBattle();
  };
  document.addEventListener('visibilitychange', () => {
    audio.setHidden(document.hidden);
    if (document.hidden) onHide();
    watch.reset();
  });
  window.addEventListener('pagehide', onHide);

  /** A building of the base was destroyed: its job is lost, and its penalty strikes now. */
  function onRuined(kind: BuildingKind): void {
    const st = baseStore.state;
    baseStore.set({ ...st, buildings: { ...st.buildings, [kind]: { ...st.buildings[kind], hp: 0 } }, jobs: st.jobs.filter((j) => j.what !== kind) });
    if (kind === 'lab') {
      // The research running is lost with its gold; with none running, the last one done (redone at half price).
      const running = research.state.active.length > 0;
      const lost = research.loseToRuin();
      syncLab();
      lab.invalidate();
      const names = lost.map((id) => researchItem(id)).filter((x) => !!x).map((x) => itemName(x)).join(', ');
      hud.showToast(names ? t(running ? 'toast.labLost' : 'toast.labLostHalf', { name: names }) : t('toast.ruined', { name: t('building.lab') }));
    } else if (kind === 'treasury') {
      const loss = treasuryLoss(baseStore.state, wallet.gold);
      if (loss > 0) wallet.gold -= loss;
      hud.showToast(loss > 0 ? t('toast.treasuryLoss', { n: loss }) : t('toast.ruined', { name: t('building.treasury') }));
    } else if (kind !== 'hq') hud.showToast(t('toast.ruined', { name: t(`building.${kind}`) }));
  }

  // Before the level: browse the guns; the one on screen when leaving is armed for placing.
  const arsenal = new Arsenal({
    // Clean render of the gun alone; the board atlas (with its soil patch) until one exists.
    portrait: (def, level, frame) =>
      portraits?.has(def) ? portraits.portrait(def, level, frame, art?.manifest.directions ?? 32) : art?.portrait(def, level, frame),
    onArt: (fn) => art?.onChange(fn) ?? (() => {}),
    directions: art?.manifest.directions ?? 32,
    close: (def) => {
      if (def) armed = def;
      selection = null;
      hud.update();
    },
    // Guns not researched yet show as locked.
    isUnlocked: (def) => game.isUnlocked(def),
    veterans: () =>
      game.base
        ? [...game.towers]
            .filter((tw) => (tw.vet ?? 0) > 0)
            .sort((a, b) => (b.vet ?? 0) - (a.vet ?? 0))
            .slice(0, 3)
            .map((tw) => ({ def: tw.def, level: tw.level, kills: tw.vet ?? 0, rank: rankName(game.rank(tw)) }))
        : [],
  });
  document.body.appendChild(arsenal.el);

  const relayout = () => {
    // In the base the arsenal, lab and level list open as windows over it.
    document.body.classList.toggle('in-base', !!game.base);
    hud.update();
    const { top, bottom } = hud.insets();
    const pad = 6;
    const view = { x: pad, y: top + pad, w: app.screen.width - 2 * pad, h: app.screen.height - top - bottom - 2 * pad };
    board.layout(view, app.screen.width, app.screen.height, app.renderer.resolution);
  };

  // A tap places the picked gun's outline, puts down a fence, or selects the gun or fence standing there.
  attachGestures(app.canvas, () => board.camera, (sx, sy) => {
    const cell = board.cellAt(sx, sy);
    const tower = cell ? game.towerAt(cell.x, cell.y) : undefined;
    const fence = cell ? game.fenceAt(cell.x, cell.y) : undefined;
    const building = cell ? game.buildingAt(cell.x, cell.y) : undefined;
    if (building) {
      // Tapping the muster opens the day's sealed order.
      if (building.kind === 'muster' && building.hp > 0) progress.markRead();
      selection = selection?.kind === 'building' && selection.what === building.kind ? null : { kind: 'building', what: building.kind };
    } else if (tower) {
      selection = selection?.kind === 'tower' && selection.id === tower.id ? null : { kind: 'tower', id: tower.id };
    } else if (fence) {
      selection = selection?.kind === 'fence' && selection.id === fence.id ? null : { kind: 'fence', id: fence.id };
    } else if (armed === 'fence') {
      // Fences are cheap and many: a tap builds one straight away.
      selection = null;
      if (cell) hud.showResult(game.buildFence(cell.x, cell.y));
    } else if (armed) {
      // Centre the footprint on the finger.
      const g = board.gridAt(sx, sy);
      const size = TOWERS[armed].size;
      selection = { kind: 'place', def: armed, cx: Math.round(g.x - size / 2), cy: Math.round(g.y - size / 2) };
      if (!game.canBuildAt(armed, selection.cx, selection.cy)) {
        const err = game.placementError(armed, selection.cx, selection.cy);
        hud.showToast(t(err === 'occupied' ? 'reason.occupied' : err ? 'hint.notBuildable' : 'reason.blocks'));
      }
    } else {
      selection = null;
    }
    hud.update();
  });

  onLangChange(() => {
    document.title = t('game.title');
    pauseMenu.invalidate();
    hud.invalidate();
    arsenal.invalidate();
    lab.invalidate();
    levels.invalidate();
    relayout();
  });
  window.addEventListener('resize', () => requestAnimationFrame(relayout));
  relayout();
  if (resumed) {
    // Back to a battle left running: it waits on the pause screen until the player is ready.
    hud.showToast(t('toast.resumed'));
    pause();
  } else if (!params.has('noarsenal') && !game.base) arsenal.open();

  // Every button clicks.
  document.addEventListener('click', (ev) => {
    if ((ev.target as HTMLElement).closest('button:not(:disabled)')) audio.play('click');
  }, { capture: true });

  /** A sound placed where it happens: panned across the screen, quieter off it. */
  const playAt = (name: SoundName, gx: number, gy: number, gain = 1) => {
    const p = board.gridToScreen(gx, gy);
    const w = app.screen.width;
    const h = app.screen.height;
    const off = p.x < -w * 0.1 || p.x > w * 1.1 || p.y < -h * 0.1 || p.y > h * 1.1;
    audio.play(name, Math.max(-1, Math.min(1, (p.x / w) * 2 - 1)) * 0.7, gain * (off ? 0.35 : 1));
  };

  // `?debug` exposes a hook for automated browser checks.
  if (new URLSearchParams(location.search).has('debug')) {
    Object.assign(window, {
      strelite: {
        gridToScreen: (x: number, y: number) => board.gridToScreen(x, y),
        game: () => game,
        board: () => board,
        camera: () => board.camera,
        arm: (def: Armed | null) => (armed = def),
        research: () => research,
        base: () => baseStore,
        audio: () => audio,
      },
    });
  }

  app.ticker.add((ticker) => {
    if (cheats.gold || cheats.instant) applyCheats();
    const frame = ticker.deltaMS / 1000;
    const alpha = loop.advance(frame);
    for (const ev of game.drainEvents()) {
      if (ev.type === 'shot') {
        board.onShot(ev.towerId, ev.projectileId);
        const tw = game.towerById(ev.towerId);
        const snd = tw && SHOT_SOUND[tw.def];
        if (tw && snd) playAt(snd, tw.x, tw.y);
      }
      else if (ev.type === 'burst') {
        board.onBurst(ev.x, ev.y, ev.radius);
        playAt('burst', ev.x, ev.y, Math.min(1, 0.6 + ev.radius * 0.2));
      }
      else if (ev.type === 'impact') {
        board.onImpact(ev.x, ev.y, ev.air);
        playAt('impact', ev.x, ev.y);
      }
      else if (ev.type === 'rail') {
        board.onRail(ev.towerId, ev.x1, ev.y1, ev.x2, ev.y2);
        playAt('railgun', ev.x1, ev.y1);
      }
      else if (ev.type === 'kill') {
        board.onKill(ev.enemyId);
        board.addFloat(`+${ev.reward}`, ev.x, ev.y, 0xf2c94c, 'air' in ENEMIES[ev.def]);
        playAt(DEATH_SOUND[ev.def], ev.x, ev.y, ev.def === 'moto' ? 0.6 : 1);
        reportOrder({ type: 'kill', def: ev.def });
      }
      else if (ev.type === 'rankUp') {
        const tw = game.towerById(ev.towerId);
        if (tw) {
          hud.showToast(t('toast.rankUp', { name: t(`tower.${tw.def}`), rank: rankName(ev.rank) }));
          board.addFloat(rankName(ev.rank), tw.x, tw.y, 0xf2c94c);
        }
      }
      else if (ev.type === 'leak') audio.play('leak');
      else if (ev.type === 'blast') {
        board.onBurst(ev.x, ev.y, ev.radius);
        playAt('burst', ev.x, ev.y);
      }
      else if (ev.type === 'strike') {
        board.onStrike(ev.kind, ev.x1, ev.y1, ev.x2, ev.y2);
        const def = game.enemies.find((e) => e.id === ev.enemyId)?.def;
        playAt(ev.kind === 'ram' ? 'ram' : def === 'tank' || def === 'fortress' ? 'tankGun' : 'rifle', ev.x1, ev.y1);
      }
      else if (ev.type === 'wrecked') {
        board.onWrecked(ev.x, ev.y, ev.size);
        playAt('wrecked', ev.x, ev.y);
        if (ev.building) onRuined(ev.building);
        else if (!ev.fence) hud.showToast(t('toast.gunWrecked'));
      }
      else if (ev.type === 'built') {
        audio.play('build');
        const tw = game.towerById(ev.towerId);
        if (tw) hud.showToast(ev.kind === 'build' ? t('toast.built', { name: t(`tower.${tw.def}`) }) : t('toast.jobDone', { name: t(`tower.${tw.def}`), n: tw.level + 1 }));
      }
      else if (ev.type === 'waveStart') {
        audio.play('waveStart');
        if (game.base && ev.wave === 1) saveBase();
        saveBattle();
      }
      else if (ev.type === 'waveClear') {
        hud.showToast(t('toast.waveClear', { n: ev.wave, bonus: ev.bonus }));
        // The last wave's stinger is the win fanfare instead.
        if (ev.wave < game.totalWaves) audio.play('waveClear');
        saveBattle();
      }
      else if (ev.type === 'won') audio.play('won');
      else if (ev.type === 'lost') audio.play('lost');
    }
    // When the battle ends, the gold it earned and did not spend goes to the treasury (plus a win bonus).
    // The flamethrowers roar while any of them pours fire.
    let flames = 0;
    for (const tw of game.towers) if (tw.def === 'greekfire' && tw.firing) flames++;
    audio.setLoop('greekfire', paused || !flames ? 0 : Math.min(1, 0.55 + 0.15 * flames));
    // Auto quality: slow frames during a wave step the graphics down, and the next start remembers it.
    if (qualityChoice === 'auto' && !paused && game.phase === 'wave' && autoStep < AUTO_STEPS - 1 && watch.frame(frame)) {
      autoStep++;
      saveAutoStep(autoStep);
      applyQuality();
      hud.showToast(t('toast.quality'));
    }
    if (banked === null && (game.phase === 'won' || game.phase === 'lost')) {
      clearBattle();
      if (game.base) {
        // The base: kills already went to the treasury; the defence reward comes on top. Nothing is wiped.
        const won = game.phase === 'won';
        banked = game.retake ? 0 : withBonus(baseTakings(game.goldEarned, won, game.level));
        research.bank(banked);
        saveBase();
        const st = baseStore.state;
        if (game.retake) {
          const next = won ? liberate(st) : { ...st, occupied: game.survivors() };
          baseStore.set(next);
          baseResult = won ? { kind: 'retakeWon', bonus: 0, n: next.buildings.hq.level + 1 } : { kind: 'retakeLost', bonus: 0, n: next.occupied?.length ?? 0 };
        } else if (won) {
          baseStore.set({ ...st, attack: st.attack + 1 });
          baseResult = { kind: 'won', bonus: banked, n: 0 };
          reportOrder({ type: 'defend', clean: game.ruined.size === 0 });
        } else if (game.hqFell) {
          // The army that took the headquarters holds it; no attacks until it is won back.
          const army = game.survivors();
          baseStore.set(occupy(st, army));
          baseResult = { kind: 'fell', bonus: banked, n: army.length };
        } else baseResult = { kind: 'broken', bonus: banked, n: 0 };
      } else {
        const won = game.phase === 'won';
        banked = withBonus(battleTakings(game.money, game.goldEarned, won, game.level));
        research.bank(banked);
        const m = game.mode === 'arc' ? 'arc' : 'path';
        const stars = progress.recordStars(m, game.level, starsFor(won, game.lives, game.startLives));
        const medalGold = stars.medals.reduce((a, b) => a + b, 0);
        if (stars.gold + medalGold > 0) research.bank(stars.gold + medalGold);
        if (stars.medals.length) audio.play('waveClear');
        if (won && game.level > wonLevel()) saveNumber(wonKey(), game.level);
        const order = won ? reportOrder({ type: 'win', mode: m, kinds: game.builtKinds.size, leaked: game.lives < game.startLives }) : 0;
        missionResult = { stars: stars.stars, before: stars.before, starGold: stars.gold, medals: stars.medals, medalCount: progress.medals, order };
      }
    }
    if (selection?.kind === 'tower' && !game.towerById(selection.id)) selection = null;
    if (selection?.kind === 'building' && !game.building(selection.what)) selection = null;
    if (selection?.kind === 'fence' && !game.fenceById(selection.id)) selection = null;
    if (game.base) board.marks = { envelope: !progress.state.read, medals: progress.medals };
    board.render(alpha, selection, armed, paused ? 0 : frame * loop.speed);
    hud.update();
  });
}

void start();
