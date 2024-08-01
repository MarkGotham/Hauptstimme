from hauptstimme import process_one
from corpus_conversion import make_contents

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--process_one_score", action="store_true", )
    parser.add_argument("--path_to_score", type=str,
                        required=False,
                        help="Path to a score.")

    args = parser.parse_args()
    if args.process_one_score:
        process_one(path_to_score=CORPUS_PATH / args.path_to_score)
        make_contents()
    else:
        parser.print_help()
