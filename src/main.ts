import { Application } from 'pixi.js';
import './style.css';
import { getLang, onLangChange, t } from './i18n';
import { BoardRenderer, type Selection } from './render/boardRenderer';
import { PALETTE } from './render/palette';
import { PortraitArt } from './render/portraitArt';
import { TowerArt } from './render/towers/spriteTowerView';
import { TICK, TOWERS, type TowerId } from './sim/content';
import { FixedStep } from './sim/fixedStep';
import { Game } from './sim/game';
import { buildPathMap } from './sim/maps';
import { levelMap } from './sim/levels';
import { LevelSelect } from './ui/levels';
import { attachGestures } from './ui/gestures';
import { Arsenal } from './ui/arsenal';
import { Hud } from './ui/hud';
import { Lab, itemName } from './ui/lab';
import { ResearchStore } from './researchStore';
import { battleTakings, researchItem } from './sim/research';

const ART_URL = `${import.meta.env.BASE_URL}art`;
const LEVEL_KEY = 'strelite.level';
const WON_KEY = 'strelite.won';

function readNumber(key: string): number {
  try {
    return Math.max(0, Math.floor(Number(localStorage.getItem(key)) || 0));
  } catch {
    return 0;
  }
}

function saveNumber(key: string, n: number): void {
  try {
    localStorage.setItem(key, String(n));
  } catch {
    // Private mode or blocked storage: it just is not remembered.
  }
}

/** Highest map level won so far. */
const wonLevel = () => readNumber(WON_KEY);

/** Map level to play: `?level=N` wins, else the last one played (never past the next unwon), else 1. */
function startLevel(): number {
  const fromUrl = Number(new URLSearchParams(location.search).get('level'));
  if (fromUrl >= 1) return Math.floor(fromUrl);
  return Math.min(Math.max(1, readNumber(LEVEL_KEY)), wonLevel() + 1);
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
  // `?fastresearch` runs research timers 600× faster, for trying the tree out.
  const research = new ResearchStore(params.has('fastresearch') ? 600 : 1);
  const newGame = (level: number) => new Game(buildPathMap(levelMap(level)), { level, upgrades: research.upgrades() });
  let game = newGame(startLevel());
  /** Gold this battle put in the treasury when it ended; null while it runs. */
  let banked: number | null = null;
  let board = new BoardRenderer(game, art, ART_URL);
  app.stage.addChild(board.root);
  let selection: Selection | null = null;
  let armed: TowerId | null = null;
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
      saveNumber(LEVEL_KEY, level);
      board.destroy();
      game = newGame(level);
      banked = null;
      board = new BoardRenderer(game, art, ART_URL);
      app.stage.addChild(board.root);
      loop = new FixedStep(TICK, (dt) => game.step(dt));
      loop.speed = speed;
      selection = null;
      armed = null;
      hud.setGame(game);
      relayout();
      arsenal.open(); // a new level starts with the arsenal again
    },
    openArsenal: () => arsenal.open(armed ?? undefined),
    openLab: () => lab.open(),
    openLevels: () => levels.open(),
    banked: () => banked ?? 0,
  });

  const levels = new LevelSelect({
    won: wonLevel,
    current: () => game.level,
    play: (level) => hud.restartAt(level),
    close: () => hud.update(),
  });
  document.body.appendChild(levels.el);

  const lab = new Lab({
    state: () => research.state,
    start: (id) => research.start(id),
    speed: research.speed,
    close: () => hud.update(),
  });
  document.body.appendChild(lab.el);
  // A finished item is announced wherever the player is; it counts from the next battle.
  window.setInterval(() => {
    const was = research.state.active?.id;
    if (was && research.tick()) {
      const item = researchItem(was);
      if (item) hud.showToast(t('toast.researchDone', { name: itemName(item) }));
      lab.invalidate();
    }
  }, 1000);

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

  // A tap places the picked gun's outline, or selects the gun standing there.
  attachGestures(app.canvas, () => board.camera, (sx, sy) => {
    const cell = board.cellAt(sx, sy);
    const tower = cell ? game.towerAt(cell.x, cell.y) : undefined;
    if (tower) {
      selection = selection?.kind === 'tower' && selection.id === tower.id ? null : { kind: 'tower', id: tower.id };
    } else if (armed) {
      // Centre the footprint on the finger.
      const g = board.gridAt(sx, sy);
      const size = TOWERS[armed].size;
      selection = { kind: 'place', def: armed, cx: Math.round(g.x - size / 2), cy: Math.round(g.y - size / 2) };
      if (!game.canBuildAt(armed, selection.cx, selection.cy)) hud.showToast(t(game.placementError(armed, selection.cx, selection.cy) === 'occupied' ? 'reason.occupied' : 'hint.notBuildable'));
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
  if (!params.has('noarsenal')) arsenal.open();

  // `?debug` exposes a hook for automated browser checks.
  if (new URLSearchParams(location.search).has('debug')) {
    Object.assign(window, {
      strelite: {
        gridToScreen: (x: number, y: number) => board.gridToScreen(x, y),
        game: () => game,
        camera: () => board.camera,
        arm: (def: TowerId | null) => (armed = def),
        research: () => research,
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
      else if (ev.type === 'waveClear') hud.showToast(t('toast.waveClear', { n: ev.wave, bonus: ev.bonus }));
    }
    // When the battle ends, the gold it earned and did not spend goes to the treasury (plus a win bonus).
    if (banked === null && (game.phase === 'won' || game.phase === 'lost')) {
      banked = battleTakings(game.money, game.goldEarned, game.phase === 'won', game.level);
      research.bank(banked);
      if (game.phase === 'won' && game.level > wonLevel()) saveNumber(WON_KEY, game.level);
    }
    if (selection?.kind === 'tower' && !game.towerById(selection.id)) selection = null;
    board.render(alpha, selection, armed, frame * loop.speed);
    hud.update();
  });
}

void start();
