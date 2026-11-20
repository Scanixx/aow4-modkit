"""Source templates for the first no-DLC example and the init command."""

HELLO_SOURCE = '''"""A complete no-DLC example. Python runs only during the build."""
from aow4modkit import ModProject, Trigger, actions, core, events

project = ModProject(
    name="Hello Realm",
    folder="HelloRealm",
    version="0.1",
    author="Your name",
    mod_id="{mod_id}",
    description="A minimal native trigger example built with AoW4 ModKit.",
    tags=("Mod",),
    readme="Install the HelloRealm folder manually after closing the game and launcher. "
           "Start a new realm. This example logs once; it has no on-screen popup. "
           "See the source example README for the complete test procedure.",
    release_notes="Initial example. Targets Age of Wonders 4 2.3.x. No DLC required.",
    workshop_description="A minimal AoW4 ModKit example for Age of Wonders 4 2.3.x. "
                         "Writes one diagnostic message on the first turn; no gameplay rewards.",
)

# Stable key -> stable resource ID, independent of file order.
# once=True is once for this global trigger, not once for every player.
project.add_trigger(Trigger(
    key="hello_realm.first_turn",
    events=[events.new_turn()],
    conditions=[core.current_round().equals(1)],
    actions=[actions.log("[AoW4ModKit] Hello Realm: first-turn trigger executed.")],
    once=True,
    comment="Minimal no-DLC example. No research, resources or units are changed.",
))
'''
