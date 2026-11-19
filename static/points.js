/*
 * Botones de sumar/restar puntos y atajos de horas en el formulario de anotar.
 * Sin dependencias ni build: el campo numérico sigue funcionando sin JS.
 */
(function () {
  'use strict';

  function clamp(valor, min, max) {
    return Math.min(max, Math.max(min, valor));
  }

  function fijarValor(input, valor) {
    input.value = valor;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  /* ➖➕ Stepper: suma o resta una hora al valor del campo. */
  function activarStepper(stepper) {
    var input = stepper.querySelector('input[type="number"]');
    if (!input) {
      return;
    }

    var min = parseInt(stepper.dataset.min || input.min || '1', 10);
    var max = parseInt(stepper.dataset.max || input.max || '24', 10);

    stepper.querySelectorAll('.stepper-btn').forEach(function (boton) {
      boton.addEventListener('click', function () {
        var delta = parseInt(boton.dataset.step || '1', 10);
        var actual = parseInt(input.value, 10);

        /* Con el campo vacío solo se puede empezar a sumar. */
        if (isNaN(actual)) {
          if (delta > 0) {
            fijarValor(input, min);
          }
          boton.blur();
          return;
        }

        fijarValor(input, clamp(actual + delta, min, max));
        boton.blur();
      });
    });

    /* Al tocar el campo se selecciona todo para poder escribir de una vez. */
    input.addEventListener('focus', function () {
      input.select();
    });
  }

  /* ⏱️ Atajos: 1 h, 2 h, 3 h… sin tener que escribir el número. */
  function activarAtajos(scope) {
    scope.querySelectorAll('[data-quick-points]').forEach(function (boton) {
      boton.addEventListener('click', function () {
        var input = document.getElementById(boton.dataset.target || 'id_points');
        if (!input) {
          return;
        }
        var min = parseInt(input.min || '1', 10);
        var max = parseInt(input.max || '24', 10);
        var valor = parseInt(boton.dataset.quickPoints, 10);
        fijarValor(input, clamp(isNaN(valor) ? min : valor, min, max));
        boton.blur();
      });
    });
  }

  function init() {
    document.querySelectorAll('.points-stepper').forEach(activarStepper);
    activarAtajos(document);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
