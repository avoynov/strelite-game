import { Application } from 'pixi.js';
import './style.css';
import { getLang, onLangChange, t } from './i18n';
import { BoardRenderer, type Selection } from './render/boardRenderer';
import { PALETTE } from './render/palette';
import { TICK } from './sim/content';
import { FixedStep } from './sim/fixedStep';
import { Game } from './sim/game';
import { buildPathMap, MEADOW } from './sim/maps';
import { Hud } from './ui/hud';

async function start(): Promise<void> {
  document.documentElement.lang = getLang();
  document.title = t('game.title');

  const app = new Application();
  await app.init({
    resizeTo: window,
    background: PALETTE.background,
    antialias: true,
    autoDensity: true,
    resolution: Math.min(window.devicePixelRatio || 1, 2),
  });
  document.getElementById('board')!.appendChild(app.canvas);

  let game = new Game(buildPathMap(MEADOW));
  let board = new BoardRenderer(game);
  app.stage.addChild(board.root);
  let selection: Selection | null = null;
  let loop = new FixedStep(TICK, (dt) => game.step(dt));

  const hud = new Hud(document.getElementById('hud')!, game, {
    getSelection: () => selection,
    setSelection: (s) => (selection = s),
    getSpeed: () => loop.speed,
    setSpeed: (s) => (loop.speed = s),
    restart: () => {
      const speed = loop.speed;
      board.root.destroy({ children: true });
      game = new Game(buildPathMap(MEADOW));
      board = new BoardRenderer(game);
      app.stage.addChild(board.root);
      loop = new FixedStep(TICK, (dt) => game.step(dt));
      loop.speed = speed;
      selection = null;
      hud.setGame(game);
      relayout();
    },
  });

  const relayout = () => {
    hud.update();
    const { top, bottom } = hud.insets();
    const pad = 8;
    board.layout(pad, top + pad, app.screen.width - 2 * pad, app.screen.height - top - bottom - 2 * pad, app.screen.width, app.screen.height);
  };

  // Tap handling on the canvas: select a tile or a tower, tap again to deselect.
  app.stage.eventMode = 'static';
  app.stage.hitArea = app.screen;
  app.stage.on('pointertap', (ev) => {
    const cell = board.cellAt(ev.global.x, ev.global.y);
    if (!cell) {
      selection = null;
      return;
    }
    if (selection && selection.x === cell.x && selection.y === cell.y) {
      selection = null;
    } else if (game.towerAt(cell.x, cell.y)) {
      selection = { kind: 'tower', ...cell };
    } else if (game.canBuildAt(cell.x, cell.y)) {
      selection = { kind: 'cell', ...cell };
    } else {
      selection = null;
      hud.showToast(t('hint.notBuildable'));
    }
    hud.update();
  });

  onLangChange(() => {
    document.title = t('game.title');
    hud.invalidate();
    relayout();
  });
  window.addEventListener('resize', () => requestAnimationFrame(relayout));
  relayout();

  // `?debug` exposes a hook for automated browser checks.
  if (new URLSearchParams(location.search).has('debug')) {
    Object.assign(window, { strelite: { cellToScreen: (x: number, y: number) => board.cellToScreen(x, y), game: () => game } });
  }

  app.ticker.add((ticker) => {
    const frame = ticker.deltaMS / 1000;
    const alpha = loop.advance(frame);
    for (const ev of game.drainEvents()) {
      if (ev.type === 'kill') board.addFloat(`+${ev.reward}`, ev.x, ev.y, 0xf2c94c);
      else if (ev.type === 'hit' && ev.overkill > 0) board.addFloat(`-${ev.overkill}`, ev.x + 0.2, ev.y, 0x9a9a9a);
      else if (ev.type === 'waveClear') hud.showToast(t('toast.waveClear', { n: ev.wave, bonus: ev.bonus }));
    }
    if (selection?.kind === 'cell' && !game.canBuildAt(selection.x, selection.y)) selection = null;
    if (selection?.kind === 'tower' && !game.towerAt(selection.x, selection.y)) selection = null;
    board.render(alpha, selection, frame);
    hud.update();
  });
}

void start();
