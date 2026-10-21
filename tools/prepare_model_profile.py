"""Prepare operator-supplied local tokenizer/model profile, offline by default."""
import argparse
import json
import sys

from almrag.embedding import ModelError
from almrag.model_setup import prepare_profile


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tokenizer',dest='tokenizer_path',required=True)
    parser.add_argument('--tokenizer-sha256',required=True)
    parser.add_argument('--digest',required=True)
    parser.add_argument('--dimension',type=int,required=True)
    parser.add_argument('--max-input-tokens',type=int,required=True)
    parser.add_argument('--model',dest='model_name',default='embeddinggemma-2')
    parser.add_argument('--output',required=True)
    parser.add_argument('--verify',action='store_true',help='Explicitly contact configured Ollama for digest/context/count calibration before writing')
    parser.add_argument('--overwrite',action='store_true',help='Atomically replace existing profile only after successful validation')
    args=vars(parser.parse_args(argv))
    try:
        result=prepare_profile(**args)
    except ModelError as exc:
        print(json.dumps({'state':'FAIL','code':exc.code}),file=sys.stderr)
        return 1
    except (ValueError,OSError,TypeError):
        print(json.dumps({'state':'FAIL','code':'MODEL_SETUP_INVALID'}),file=sys.stderr)
        return 1
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
