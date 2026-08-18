{% macro to_life_number(column) %}
    upper(trim({{ column }}))
{% endmacro %}
