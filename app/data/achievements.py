# Hardcoded achievement definitions. Adding a new achievement = add one entry here
# and a corresponding checker function in achievement_service.py. No DB migration needed.
ACHIEVEMENTS: dict[str, dict] = {
    "play_numbers": {
        "title": "Numbers",
        "description": "Complete a Numbers puzzle.",
        "unlocks_avatar_id": "numbers",
    },
    "play_words": {
        "title": "Words",
        "description": "Complete a Words puzzle.",
        "unlocks_avatar_id": "words",
    },
    "rank_first_global": {
        "title": "World #1",
        "description": "Finish #1 globally in any puzzle.",
        "unlocks_color_id": "gold",
    },
    "rank_top_ten": {
        "title": "World Top 10",
        "description": "Finish in the global top 10 in any puzzle.",
        "unlocks_color_id": "silver",
    },
    "daily_sweep": {
        "title": "Perfect Day",
        "description": "Finish #1 globally in every puzzle in a single day.",
        "unlocks_color_id": "black",
    },
    "add_friend": {
        "title": "Social Butterfly",
        "description": "Add your first friend.",
        "unlocks_avatar_id": "friend",
    },
    "massive": {
        "title": "Absolutely Massive",
        "description": "Make a number of at least 100 million in Numbers.",
        "unlocks_avatar_id": "flex",
    },
    "nice": {
        "title": "Nice",
        "description": "Make exactly 69 in Numbers.",
        "unlocks_avatar_id": "taunt",
    },
    "blackout": {
        "title": "Blackout",
        "description": "Complete all puzzles in a single day.",
        "unlocks_avatar_id": "sunglasses",
    },
    "hit_target": {
        "title": "Hit the Target",
        "description": "Get exactly the target in Numbers.",
        "unlocks_avatar_id": "bullseye",
    },
    "numbers_streak_5": {
        "title": "Numbers Novice",
        "description": "Reach a 5-day Numbers streak.",
        "unlocks_avatar_id": "fire",
    },
    "numbers_streak_10": {
        "title": "Numbers Regular",
        "description": "Reach a 10-day Numbers streak.",
        "unlocks_avatar_id": "bolt_icon",
    },
    "numbers_streak_25": {
        "title": "Numbers Expert",
        "description": "Reach a 25-day Numbers streak.",
        "unlocks_avatar_id": "star_icon",
    },
    "numbers_streak_100": {
        "title": "Numbers Veteran",
        "description": "Reach a 100-day Numbers streak.",
        "unlocks_avatar_id": "shield",
    },
    "numbers_streak_250": {
        "title": "Numbers Legend",
        "description": "Reach a 250-day Numbers streak.",
        "unlocks_avatar_id": "coffee",
    },
    "numbers_streak_500": {
        "title": "Numbers Master",
        "description": "Reach a 500-day Numbers streak.",
        "unlocks_avatar_id": "anchor",
    },
    "words_streak_5": {
        "title": "Words Novice",
        "description": "Reach a 5-day Words streak.",
        "unlocks_avatar_id": "heart",
    },
    "words_streak_10": {
        "title": "Words Regular",
        "description": "Reach a 10-day Words streak.",
        "unlocks_avatar_id": "music",
    },
    "words_streak_25": {
        "title": "Words Expert",
        "description": "Reach a 25-day Words streak.",
        "unlocks_avatar_id": "snowflake",
    },
    "words_streak_100": {
        "title": "Words Veteran",
        "description": "Reach a 100-day Words streak.",
        "unlocks_avatar_id": "sun_icon",
    },
    "words_streak_250": {
        "title": "Words Legend",
        "description": "Reach a 250-day Words streak.",
        "unlocks_avatar_id": "lotus",
    },
    "words_streak_500": {
        "title": "Words Master",
        "description": "Reach a 500-day Words streak.",
        "unlocks_avatar_id": "pizza",
    },
    "numbers_streak_365": {
        "title": "Year of Numbers",
        "description": "Reach a 365-day Numbers streak.",
        "unlocks_color_id": "purple",
    },
    "words_streak_365": {
        "title": "Year of Words",
        "description": "Reach a 365-day Words streak.",
        "unlocks_color_id": "teal",
    },
    "numbers_streak_1000": {
        "title": "Numbers God",
        "description": "Reach a 1000-day Numbers streak.",
        "unlocks_color_id": "pink",
    },
    "words_streak_1000": {
        "title": "Words God",
        "description": "Reach a 1000-day Words streak.",
        "unlocks_color_id": "lime",
    },
    "play_routes": {
        "title": "Routes",
        "description": "Complete a Routes puzzle.",
        "unlocks_avatar_id": "route",
    },
    "routes_streak_5": {
        "title": "Routes Novice",
        "description": "Reach a 5-day Routes streak.",
        "unlocks_avatar_id": "map",
    },
    "routes_streak_10": {
        "title": "Routes Regular",
        "description": "Reach a 10-day Routes streak.",
        "unlocks_avatar_id": "compass",
    },
    "routes_streak_25": {
        "title": "Routes Expert",
        "description": "Reach a 25-day Routes streak.",
        "unlocks_avatar_id": "trail",
    },
    "routes_streak_100": {
        "title": "Routes Veteran",
        "description": "Reach a 100-day Routes streak.",
        "unlocks_avatar_id": "globe",
    },
    "routes_streak_250": {
        "title": "Routes Legend",
        "description": "Reach a 250-day Routes streak.",
        "unlocks_avatar_id": "mountain",
    },
    "routes_streak_365": {
        "title": "Year of Routes",
        "description": "Reach a 365-day Routes streak.",
        "unlocks_color_id": "orange",
    },
    "routes_streak_500": {
        "title": "Routes Master",
        "description": "Reach a 500-day Routes streak.",
        "unlocks_avatar_id": "wave",
    },
    "routes_streak_1000": {
        "title": "Routes God",
        "description": "Reach a 1000-day Routes streak.",
        "unlocks_color_id": "blue",
    },
    "maze_for_mice": {
        "title": "Maze for Mice",
        "description": "Complete a 4x4 Routes puzzle.",
        "unlocks_avatar_id": "mouse",
    },
    "walk_in_the_park": {
        "title": "Walk in the Park",
        "description": "Complete a 5x5 Routes puzzle.",
        "unlocks_avatar_id": "tree",
    },
    "roadtrip": {
        "title": "Roadtrip",
        "description": "Complete a 6x6 Routes puzzle.",
        "unlocks_avatar_id": "car",
    },
    "goose_egg": {
        "title": "Goose Egg",
        "description": "Finish a Words game with a score of zero.",
        "unlocks_avatar_id": "egg",
    },
    "early_bird": {
        "title": "Early Bird",
        "description": "Complete a puzzle between 8:00am and 8:30am.",
        "unlocks_avatar_id": "raven",
    },
    "night_owl": {
        "title": "Night Owl",
        "description": "Complete a puzzle between midnight and 5am.",
        "unlocks_avatar_id": "owl",
    },
    "hippopotomonstrosesquippedaliophobia": {
        "title": "Antidisestablishmentarianism",
        "description": "Play a word at least 8 letters long in Words.",
        "unlocks_avatar_id": "eight",
    },
    "meta": {
        "title": "Meta",
        "description": "Play the word 'words' in Words.",
        "unlocks_avatar_id": "meta",
    },
    "queen": {
        "title": "Quite Queenly",
        "description": "Use the Qu tile in Words.",
        "unlocks_avatar_id": "queen",
    },
    "hundredth_day": {
        "title": "Hundredth Day",
        "description": "Complete a puzzle on the 100th day of the year.",
        "unlocks_avatar_id": "cake",
    },
    "santa": {
        "title": "Father Christmas",
        "description": "Complete a puzzle on Christmas Day.",
        "unlocks_avatar_id": "santa",
    },
    "completionist": {
        "title": "Completionist",
        "description": "Unlock every other achievement.",
        "unlocks_icon_color_id": "silver",
    },
}
