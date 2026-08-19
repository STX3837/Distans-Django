import json

from django import forms
from django.utils.safestring import mark_safe


class StockStepperWidget(forms.NumberInput):
    def __init__(self, attrs=None):
        base_attrs = {'min': 0, 'step': 1, 'inputmode': 'numeric'}
        if attrs:
            base_attrs.update(attrs)
        super().__init__(attrs=base_attrs)

    def render(self, name, value, attrs=None, renderer=None):
        final_attrs = self.build_attrs(self.attrs, attrs)
        final_attrs.setdefault('min', 0)
        final_attrs.setdefault('step', 1)
        final_attrs.setdefault('inputmode', 'numeric')

        input_html = super().render(name, value, final_attrs, renderer)
        input_id = final_attrs.get('id', f'id_{name}')

        widget_html = mark_safe(
            '<style>'
            '.stock-stepper{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}'
            '.stock-stepper__input input{width:120px;text-align:center;}'
            '.stock-stepper__button{width:40px;height:40px;border:1px solid #1f2937;border-radius:8px;background:#f3f4f6;color:#111827;font-size:20px;line-height:1;font-weight:700;cursor:pointer;}'
            '.stock-stepper__button:hover{background:#e5e7eb;}'
            '.stock-stepper__button:focus{outline:2px solid #2563eb;outline-offset:2px;}'
            '</style>'
            '<div class="stock-stepper" data-stock-stepper>'
            '<button type="button" class="stock-stepper__button" data-stock-stepper-action="decrease" aria-label="Reducir stock">-</button>'
            '<div class="stock-stepper__input">' + input_html + '</div>'
            '<button type="button" class="stock-stepper__button" data-stock-stepper-action="increase" aria-label="Aumentar stock">+</button>'
            '</div>'
        )

        script = mark_safe(
            f"""
<script>
(function() {{
    var input = document.getElementById({json.dumps(input_id)});
    if (!input || input.dataset.stockStepperReady === '1') {{
        return;
    }}

    input.dataset.stockStepperReady = '1';
    var wrapper = input.closest('[data-stock-stepper]');
    if (!wrapper) {{
        return;
    }}

    var decrease = wrapper.querySelector('[data-stock-stepper-action="decrease"]');
    var increase = wrapper.querySelector('[data-stock-stepper-action="increase"]');

    var getValue = function() {{
        var currentValue = parseInt(input.value, 10);
        return isNaN(currentValue) ? 0 : currentValue;
    }};

    var setValue = function(nextValue) {{
        input.value = Math.max(0, nextValue);
        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        input.focus();
    }};

    decrease.addEventListener('click', function() {{
        setValue(getValue() - 1);
    }});

    increase.addEventListener('click', function() {{
        setValue(getValue() + 1);
    }});
}})();
</script>
"""
        )

        return widget_html + script