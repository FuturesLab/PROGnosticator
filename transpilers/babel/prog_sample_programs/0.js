// This program demonstrates shadowing variable in nested block using let
function func1() {
  let x = 1;
  {
    let x = 2;
    return x;
  }
}

function main() {
  let res = func1();
  console.log(res);
}

main();