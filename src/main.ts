import { Application } from 'pixi.js';
import './style.css';
import { getLang, onLangChange, t } from './i18n';
import { BoardRenderer, type Selection } from './render/boardRenderer';
import { PALETTE } from './render/palette';
import { TowerArt } from './render/towers/spriteTowerView';
import { TICK, TOWERS, type TowerId } from './sim/content';
import { FixedStep } from './sim/fixedStep';
import { Game } from './sim/game';
import { buildPathMap, MEADOW } from './sim/maps';
import { attachGestures } from './ui/gestures';
import { Arsenal } from './ui/arsenal';
import { Hud } from './ui/hud';

const ART_URL = `${import.meta.env.BASE_URL}art`;

async function start(): Promise<void> {
  document.documentElement.lang = getLang();
  document.title = t('game.title');

  const app = new Application();
  const [art] = await Promise.all([
    TowerArt.load(ART_URL),
    app.init({
      resizeTo: window,
      background: PALETTE.background,
      antialias: true,
      autoDensity: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
    }),
  ]);
  await art?.preload();
  document.getElementById('board')!.appendChild(app.canvas);

  let game = new Game(buildPathMap(MEADOW));
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
    restart: () => {
      const speed = loop.speed;
      board.destroy();
      game = new Game(buildPathMap(MEADOW));
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
  });

  // Before the level: browse the guns; the one on screen when leaving is armed for placing.
  const arsenal = new Arsenal({
    portrait: (def, level, frame) => art?.portrait(def, level, frame),
    onArt: (fn) => art?.onChange(fn) ?? (() => {}),
    directions: art?.manifest.directions ?? 32,
    close: (def) => {
      armed = def;
      selection = null;
      hud.update();
    },
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
    relayout();
  });
  window.addEventListener('resize', () => requestAnimationFrame(relayout));
  relayout();
  if (!new URLSearchParams(location.search).has('noarsenal')) arsenal.open();

  // `?debug` exposes a hook for automated browser checks.
  if (new URLSearchParams(location.search).has('debug')) {
    Object.assign(window, {
      strelite: {
        gridToScreen: (x: number, y: number) => board.gridToScreen(x, y),
        game: () => game,
        camera: () => board.camera,
        arm: (def: TowerId | null) => (armed = def),
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
      else if (ev.type === 'kill') {
        board.onKill(ev.enemyId);
        board.addFloat(`+${ev.reward}`, ev.x, ev.y, 0xf2c94c);
      }
      else if (ev.type === 'waveClear') hud.showToast(t('toast.waveClear', { n: ev.wave, bonus: ev.bonus }));
    }
    if (selection?.kind === 'tower' && !game.towerById(selection.id)) selection = null;
    board.render(alpha, selection, armed, frame * loop.speed);
    hud.update();
  });
}

void start();
