import { Application } from 'pixi.js';
import './style.css';
import { getLang, onLangChange, t } from './i18n';
import { BoardRenderer, type Armed, type Selection } from './render/boardRenderer';
import { PALETTE } from './render/palette';
import { PortraitArt } from './render/portraitArt';
import { TowerArt } from './render/towers/spriteTowerView';
import { TICK, TOWERS } from './sim/content';
import { FixedStep } from './sim/fixedStep';
import { Game } from './sim/game';
import { buildArcMap, buildPathMap, type Mode } from './sim/maps';
import { levelArcMap, levelMap } from './sim/levels';
import { LevelSelect } from './ui/levels';
import { attachGestures } from './ui/gestures';
import { Arsenal } from './ui/arsenal';
import { Hud } from './ui/hud';
import { Lab, itemName } from './ui/lab';
import { ResearchStore } from './researchStore';
import { BaseStore } from './baseStore';
import { battleTakings, researchItem } from './sim/research';
import { BASE_MAP, baseTakings, HQ_LEVELS, LAB_LEVELS, lossSale } from './sim/base';
import { attackStrength, defenceStrength } from './sim/strength';
import type { BaseHud } from './ui/hud';

const ART_URL = `${import.meta.env.BASE_URL}art`;
const MODE_KEY = 'strelite.mode';

const MODES: readonly Mode[] = ['path', 'arc', 'siege'];
const asMode = (v: string | null): Mode | null => MODES.find((m) => m === v) ?? null;

function readMode(): Mode {
  const fromUrl = asMode(new URLSearchParams(location.search).get('mode'));
  if (fromUrl) return fromUrl;
  try {
    return asMode(localStorage.getItem(MODE_KEY)) ?? 'path';
  } catch {
    return 'path';
  }
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

/** Map level to play: `?level=N` wins, else the last one played (never past the next unwon), else 1. */
function startLevel(): number {
  const fromUrl = Number(new URLSearchParams(location.search).get('level'));
  if (fromUrl >= 1) return Math.floor(fromUrl);
  return Math.min(Math.max(1, readNumber(levelKey())), wonLevel() + 1);
}

async function start(): Promise<void> {
  document.documentElement.lang = getLang();
  document.title = t('game.title');

  const app = new Application();
  const [art, portraits] = await Promise.all([
    TowerArt.load(ART_URL),
    PortraitArt.load(ART_URL),
    app.init({
      resizeTo: window,
      background: PALETTE.background,
      antialias: true,
      autoDensity: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
    }),
  ]);
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
    const l = baseStore.state.lab;
    research.setLab({ level: l?.level ?? 0, standing: l !== null });
  };
  baseStore.settle();
  syncLab();
  /** Once an attack on the base is over: its reward, and (base lost) what the remains sold for. */
  let baseResult: { bonus: number; sale: number } | null = null;

  const newGame = (level: number) => {
    if (mode === 'siege') {
      // The base: one fixed field; the attack number comes from the saved base.
      baseStore.settle();
      syncLab();
      return new Game(buildArcMap(BASE_MAP, 'siege'), {
        level: baseStore.state.attack,
        upgrades: research.upgrades(),
        base: {
          get state() {
            return baseStore.state;
          },
          wallet,
          speed: fast,
        },
      });
    }
    return new Game(mode === 'path' ? buildPathMap(levelMap(level)) : buildArcMap(levelArcMap(level), mode), { level, upgrades: research.upgrades() });
  };
  let game = newGame(startLevel());

  /** Base mode: write what stands into the saved base (the building levels and jobs stay the store's). */
  const saveBase = () => {
    if (!game.base || game.phase === 'lost') return;
    const snap = game.snapshot();
    const st = baseStore.state;
    // A building raised while this battle ran keeps its new level; damage taken carries over.
    const carry = (hp: number, from: number, to: number) => Math.max(1, Math.min(to, hp + to - from));
    const hq = { level: st.hq.level, hp: carry(snap.hq.hp, HQ_LEVELS[snap.hq.level]!.hp, HQ_LEVELS[st.hq.level]!.hp) };
    const lab = st.lab && snap.lab ? { level: st.lab.level, hp: carry(snap.lab.hp, LAB_LEVELS[snap.lab.level]!.hp, LAB_LEVELS[st.lab.level]!.hp) } : st.lab;
    baseStore.set({ ...st, hq, lab, guns: snap.guns, fences: snap.fences });
  };
  let enemyStrength = { attack: 0, value: 0 };
  const baseHud: BaseHud = {
    state: () => baseStore.state,
    startJob: (what) => {
      saveBase();
      const err = baseStore.startJob(what, wallet);
      if (!err) syncLab();
      return err;
    },
    strength: () => {
      if (enemyStrength.attack !== game.level) enemyStrength = { attack: game.level, value: attackStrength(game.level) };
      return { you: defenceStrength(game), enemy: enemyStrength.value };
    },
    result: () => baseResult,
    speed: fast,
  };
  /** Gold this battle put in the treasury when it ended; null while it runs. */
  let banked: number | null = null;
  let board = new BoardRenderer(game, art, ART_URL);
  app.stage.addChild(board.root);
  let selection: Selection | null = null;
  let armed: Armed | null = null;
  let loop = new FixedStep(TICK, (dt) => game.step(dt));

  const hud = new Hud(document.getElementById('hud')!, game, {
    getSelection: () => selection,
    setSelection: (s) => (selection = s),
    getArmed: () => armed,
    setArmed: (def) => {
      armed = def;
      selection = null;
    },
    towerIcon: (def) => art?.iconCss(def, 52) ?? '',
    getSpeed: () => loop.speed,
    setSpeed: (s) => (loop.speed = s),
    restart: (level = game.level) => {
      const speed = loop.speed;
      saveNumber(levelKey(), level);
      board.destroy();
      saveBase();
      game = newGame(level);
      banked = null;
      baseResult = null;
      board = new BoardRenderer(game, art, ART_URL);
      app.stage.addChild(board.root);
      loop = new FixedStep(TICK, (dt) => game.step(dt));
      loop.speed = speed;
      selection = null;
      armed = null;
      hud.setGame(game);
      relayout();
      if (!game.base) arsenal.open(); // a new level starts with the arsenal again
    },
    openArsenal: () => arsenal.open(armed && armed !== 'fence' ? armed : undefined),
    openLab: () => lab.open(),
    openLevels: () => levels.open(),
    banked: () => banked ?? 0,
    base: () => (game.base ? baseHud : null),
  });

  const levels = new LevelSelect({
    won: wonLevel,
    current: () => (game.mode === mode ? game.level : 0),
    mode: () => mode,
    setMode: (m) => {
      mode = m;
      saveString(MODE_KEY, m);
    },
    play: (level) => hud.restartAt(level),
    attack: () => baseStore.state.attack,
    close: () => hud.update(),
  });
  document.body.appendChild(levels.el);

  const lab = new Lab({
    state: () => research.state,
    lab: () => research.lab,
    start: (id) => research.start(id),
    speed: research.speed,
    close: () => hud.update(),
  });
  document.body.appendChild(lab.el);
  // A finished item is announced wherever the player is; it counts from the next battle.
  let doneCount = research.state.done.length;
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
      if (after.hq.level !== before.hq.level) hud.showToast(t('toast.jobDone', { name: t('building.hq'), n: after.hq.level + 1 }));
      if (after.lab && after.lab.level !== before.lab?.level) hud.showToast(t('toast.jobDone', { name: t('building.lab'), n: after.lab.level + 1 }));
      // In peace the base is rebuilt at once with the new levels; during an attack they count from the next.
      if (game.base && game.phase === 'build' && game.wave === 0) hud.restartAt(game.level);
    }
  }, 1000);
  document.addEventListener('visibilitychange', saveBase);
  window.addEventListener('pagehide', saveBase);

  // Before the level: browse the guns; the one on screen when leaving is armed for placing.
  const arsenal = new Arsenal({
    // Clean render of the gun alone; the board atlas (with its soil patch) until one exists.
    portrait: (def, level, frame) =>
      portraits?.has(def) ? portraits.portrait(def, level, frame, art?.manifest.directions ?? 32) : art?.portrait(def, level, frame),
    onArt: (fn) => art?.onChange(fn) ?? (() => {}),
    directions: art?.manifest.directions ?? 32,
    close: (def) => {
      armed = def;
      selection = null;
      hud.update();
    },
    // Guns not researched yet show as locked.
    isUnlocked: (def) => game.isUnlocked(def),
  });
  document.body.appendChild(arsenal.el);

  const relayout = () => {
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
    hud.invalidate();
    arsenal.invalidate();
    lab.invalidate();
    levels.invalidate();
    relayout();
  });
  window.addEventListener('resize', () => requestAnimationFrame(relayout));
  relayout();
  if (!params.has('noarsenal') && !game.base) arsenal.open();

  // `?debug` exposes a hook for automated browser checks.
  if (new URLSearchParams(location.search).has('debug')) {
    Object.assign(window, {
      strelite: {
        gridToScreen: (x: number, y: number) => board.gridToScreen(x, y),
        game: () => game,
        camera: () => board.camera,
        arm: (def: Armed | null) => (armed = def),
        research: () => research,
        base: () => baseStore,
      },
    });
  }

  app.ticker.add((ticker) => {
    const frame = ticker.deltaMS / 1000;
    const alpha = loop.advance(frame);
    for (const ev of game.drainEvents()) {
      if (ev.type === 'shot') board.onShot(ev.towerId, ev.projectileId);
      else if (ev.type === 'burst') board.onBurst(ev.x, ev.y, ev.radius);
      else if (ev.type === 'impact') board.onImpact(ev.x, ev.y);
      else if (ev.type === 'rail') board.onRail(ev.towerId, ev.x1, ev.y1, ev.x2, ev.y2);
      else if (ev.type === 'kill') {
        board.onKill(ev.enemyId);
        board.addFloat(`+${ev.reward}`, ev.x, ev.y, 0xf2c94c);
      }
      else if (ev.type === 'strike') board.onStrike(ev.kind, ev.x1, ev.y1, ev.x2, ev.y2);
      else if (ev.type === 'wrecked') {
        board.onWrecked(ev.x, ev.y, ev.size);
        if (ev.building === 'lab') {
          // The laboratory is gone: research stops and its building job is lost.
          const st = baseStore.state;
          baseStore.set({ ...st, lab: null, jobs: st.jobs.filter((j) => j.what !== 'lab') });
          syncLab();
          lab.invalidate();
          hud.showToast(t('toast.labDown'));
        } else if (!ev.fence && !ev.building) hud.showToast(t('toast.gunWrecked'));
      }
      else if (ev.type === 'built') {
        const tw = game.towerById(ev.towerId);
        if (tw) hud.showToast(ev.kind === 'build' ? t('toast.built', { name: t(`tower.${tw.def}`) }) : t('toast.jobDone', { name: t(`tower.${tw.def}`), n: tw.level + 1 }));
      }
      else if (ev.type === 'waveStart' && game.base && ev.wave === 1) saveBase();
      else if (ev.type === 'waveClear') hud.showToast(t('toast.waveClear', { n: ev.wave, bonus: ev.bonus }));
    }
    // When the battle ends, the gold it earned and did not spend goes to the treasury (plus a win bonus).
    if (banked === null && (game.phase === 'won' || game.phase === 'lost')) {
      if (game.base) {
        // The base: kills already went to the treasury; the defence reward comes on top.
        const won = game.phase === 'won';
        banked = baseTakings(game.goldEarned, won, game.level);
        research.bank(banked);
        if (won) {
          saveBase();
          baseStore.set({ ...baseStore.state, attack: baseStore.state.attack + 1 });
          baseResult = { bonus: banked, sale: 0 };
        } else {
          // The headquarters fell: what still stands is sold off and the base starts over.
          const snap = game.snapshot();
          const sale = lossSale({ ...baseStore.state, guns: snap.guns, fences: snap.fences, lab: game.lab ? baseStore.state.lab : null });
          research.bank(sale);
          baseStore.reset();
          syncLab();
          baseResult = { bonus: banked, sale };
        }
      } else {
        banked = battleTakings(game.money, game.goldEarned, game.phase === 'won', game.level);
        research.bank(banked);
        if (game.phase === 'won' && game.level > wonLevel()) saveNumber(wonKey(), game.level);
      }
    }
    if (selection?.kind === 'tower' && !game.towerById(selection.id)) selection = null;
    if (selection?.kind === 'building' && !(selection.what === 'hq' ? game.hq : game.lab)) selection = null;
    if (selection?.kind === 'fence' && !game.fenceById(selection.id)) selection = null;
    board.render(alpha, selection, armed, frame * loop.speed);
    hud.update();
  });
}

void start();
