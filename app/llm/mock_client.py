"""Offline LLM stand-in that builds plausible, deterministic recipes from the user's ingredients."""

import time
import zlib
from dataclasses import dataclass

from app.llm.schemas import (
    Difficulty,
    RecipeDetails,
    RecipeIngredient,
    RecipeSuggestion,
    Step,
)


@dataclass(frozen=True)
class _Template:
    title: str
    description: str
    minutes: int
    difficulty: Difficulty
    steps: tuple[tuple[str, int], ...]
    extras: tuple[str, ...] = ()  # ingredients the dish needs beyond what the user has


# Placeholders: {a} main ingredient, {b} second ingredient, {all} every available ingredient,
# {extras} the missing ingredients.
_COMPLETE_TEMPLATES = (
    _Template(
        "{A} & {B} Skillet",
        "A quick one-pan dish that brings out the best of your {a} and {b}.",
        25,
        "easy",
        (
            ("Wash and chop the {all} into bite-sized pieces.", 5),
            ("Heat a splash of oil in a large skillet over medium-high heat.", 2),
            ("Add the {a} and cook until it starts to brown.", 6),
            ("Stir in the remaining ingredients and cook until tender.", 8),
            ("Season with salt and pepper, then serve hot.", 2),
        ),
    ),
    _Template(
        "Rustic {A} Bake",
        "Oven-baked comfort food with {a} and everything else from your pantry.",
        45,
        "medium",
        (
            ("Preheat the oven to 200 °C (390 °F) and lightly oil a baking dish.", 10),
            ("Slice the {all} evenly so everything cooks at the same rate.", 8),
            ("Layer the ingredients in the dish, seasoning each layer.", 5),
            ("Bake until golden on top and cooked through.", 25),
            ("Rest for 5 minutes before serving.", 5),
        ),
    ),
    _Template(
        "Hearty {A} Soup",
        "A warming soup built around {a}, simmered with {b}.",
        40,
        "easy",
        (
            ("Dice the {all}.", 6),
            ("Sweat the {b} in a little oil in a large pot until soft.", 5),
            ("Add the {a} and enough water to cover by two fingers.", 2),
            ("Simmer gently until everything is tender.", 22),
            ("Blend partially for body, season to taste and serve.", 5),
        ),
    ),
    _Template(
        "Warm {A} & {B} Salad Bowl",
        "A bright, filling bowl that showcases {a} and {b} with a simple dressing.",
        20,
        "easy",
        (
            ("Prepare the {all}: wash, peel and cut as needed.", 6),
            ("Quickly sauté the {a} in a hot pan until just cooked.", 5),
            ("Whisk oil, salt and pepper into a simple dressing.", 2),
            ("Toss everything together while the {a} is still warm.", 3),
            ("Plate in bowls and serve immediately.", 1),
        ),
    ),
)

_EXTENDED_TEMPLATES = (
    _Template(
        "{A} Pasta Primavera",
        "Classic pasta tossed with {a} and {b}; just grab {extras}.",
        30,
        "medium",
        (
            ("Bring a large pot of salted water to the boil.", 8),
            ("Cook the pasta until al dente, reserving a cup of pasta water.", 10),
            ("Meanwhile, sauté the {all} in oil until tender.", 8),
            ("Toss the pasta with the vegetables and a splash of pasta water.", 2),
            ("Finish with grated parmesan and serve.", 2),
        ),
        ("pasta", "parmesan"),
    ),
    _Template(
        "{A} Fried Rice",
        "Takeaway-style fried rice with {a}; you'll need {extras}.",
        25,
        "easy",
        (
            ("Cook the rice and spread it out to cool (day-old rice is best).", 15),
            ("Dice the {all} finely.", 5),
            ("Stir-fry the {a} in a very hot wok with a little oil.", 4),
            ("Add the rice and remaining ingredients, tossing constantly.", 4),
            ("Season with soy sauce and serve straight from the wok.", 1),
        ),
        ("rice", "soy sauce"),
    ),
    _Template(
        "Garlic Butter {A}",
        "Rich, glossy {a} finished in garlic butter; pick up {extras}.",
        20,
        "easy",
        (
            ("Prepare the {all} and mince the garlic.", 5),
            ("Melt the butter in a pan over medium heat.", 2),
            ("Add the garlic and cook for 30 seconds until fragrant.", 1),
            ("Add the {a} and the rest, basting with the butter until cooked.", 10),
            ("Season and spoon the pan juices over to serve.", 1),
        ),
        ("garlic", "butter"),
    ),
    _Template(
        "{A} Street Tacos",
        "Charred {a} and {b} piled into warm tortillas; add {extras}.",
        25,
        "medium",
        (
            ("Cut the {all} into small strips.", 5),
            ("Char the {a} in a very hot dry pan.", 6),
            ("Add the remaining ingredients and cook until just tender.", 5),
            ("Warm the tortillas in the same pan.", 3),
            ("Fill the tortillas and finish with a squeeze of lime.", 2),
        ),
        ("tortillas", "lime"),
    ),
)

_QUANTITIES = ("200 g", "1 medium", "150 g", "2 pieces", "1 cup", "100 g")


def _fill(text: str, available: list[str], extras: list[str]) -> str:
    a = available[0]
    if len(available) > 1:
        b = available[1]
    else:
        b = a
        text = text.replace(" & {B}", "")  # avoid "Eggs & Eggs Skillet"
    return text.format(
        a=a,
        b=b,
        A=a.title(),
        B=b.title(),
        all=", ".join(available),
        extras=" and ".join(extras),
    )


class MockLLMClient:
    """Returns 2 recipes using only the given ingredients and 1 that needs a few extras."""

    def __init__(self, latency_seconds: float = 0.5) -> None:
        self._latency = latency_seconds

    def _pause(self) -> None:
        if self._latency:
            time.sleep(self._latency)

    def suggest_recipes(self, available_ingredients: list[str]) -> list[RecipeSuggestion]:
        self._pause()
        available = available_ingredients
        seed = zlib.crc32(",".join(sorted(available)).encode())  # stable across runs, unlike hash()

        complete = [
            _COMPLETE_TEMPLATES[(seed + offset) % len(_COMPLETE_TEMPLATES)] for offset in (0, 1)
        ]
        suggestions = [self._to_suggestion(t, available, []) for t in complete]

        for offset in range(len(_EXTENDED_TEMPLATES)):
            template = _EXTENDED_TEMPLATES[(seed + offset) % len(_EXTENDED_TEMPLATES)]
            extras = [e for e in template.extras if e not in available]
            if extras:
                suggestions.append(self._to_suggestion(template, available, extras))
                break
        else:
            # The user already has every extra the templates know about; still offer an upgrade.
            template = _EXTENDED_TEMPLATES[seed % len(_EXTENDED_TEMPLATES)]
            suggestions.append(self._to_suggestion(template, available, ["fresh herbs"]))
        return suggestions

    def get_recipe_details(
        self, suggestion: RecipeSuggestion, available_ingredients: list[str]
    ) -> RecipeDetails:
        self._pause()
        available = available_ingredients
        extras = suggestion.missing_ingredients
        template = self._find_template(suggestion.title, available, extras)

        ingredients = [
            RecipeIngredient(name=name, quantity=_QUANTITIES[i % len(_QUANTITIES)])
            for i, name in enumerate(available)
        ]
        ingredients += [
            RecipeIngredient(name=name, quantity="to taste" if name == "soy sauce" else "100 g",
                             is_missing=True)
            for name in extras
        ]
        steps = [
            Step(number=i, instruction=_fill(text, available, extras), duration_minutes=minutes)
            for i, (text, minutes) in enumerate(template.steps, start=1)
        ]
        tips = [
            "Taste as you go and adjust the seasoning at the end.",
            "Leftovers keep in the fridge for up to 2 days.",
        ]
        if extras:
            tips.insert(0, f"No {extras[0]}? Use whatever similar ingredient you have on hand.")

        return RecipeDetails(
            title=suggestion.title,
            servings=2,
            ingredients=ingredients,
            steps=steps,
            tips=tips,
        )

    @staticmethod
    def _to_suggestion(
        template: _Template, available: list[str], extras: list[str]
    ) -> RecipeSuggestion:
        return RecipeSuggestion(
            title=_fill(template.title, available, extras),
            short_description=_fill(template.description, available, extras),
            missing_ingredients=extras,
            estimated_time_minutes=template.minutes,
            difficulty=template.difficulty,
        )

    @staticmethod
    def _find_template(title: str, available: list[str], extras: list[str]) -> _Template:
        for template in _COMPLETE_TEMPLATES + _EXTENDED_TEMPLATES:
            if _fill(template.title, available, extras) == title:
                return template
        return _COMPLETE_TEMPLATES[0]
