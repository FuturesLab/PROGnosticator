# PROGnosticatoring.py

Dependencies:
- **Node.js**: [install from here](https://github.com/nodejs/node).
- **Babel**: [install from here](https://github.com/babel/babel).


This script (`PROGnosticatoring.py`) automates the process of compiling ES6+ JS programs using node, transpiling them to ES5 using `babel`, and checking if the output of the ES6+ JS and ES5 JS programs match.

## Usage

- You must pass two arguments when running the script:
  ```bash
  python3 PROGnosticatoring.py <input_js_folder> <campaign_id>
  ```

- The `<input_js_folder>` should contain PROGnosticator-generated `.js` files.
We here provide some sample PROGnosticator-generated JS programs in `prog_sample_programs` folder.

- You must pass two arguments when running the script:

```bash
  python3 PROGnosticatoring.py <input_js_folder> <campaign_id>

  # for example
  python3 prog_sample_programs 1
```

## Output Directory Structure

The script creates the following folders under a `campaign_<campaign_id>` directory:

- `babel_project/` : Directory for processing each input-output pair
- `babel_crash.txt`  : This tracks input js files causing babel crash
- `divergence_output.txt` : This tracks which input js file causing divergence and saving the output
- `input_js_failure.txt` : This tracks which input js file is invalid
- `output_js_failure.txt` : This tracks which ouput js file is invalid
- `summary.txt` : Overall Summary of the previous tracking numbers, total time.

The script creates the following folders under a `campaign_<campaign_id>` directory:

## Result Summary

The final summary is written to:
```
summary.txt
```