// JavaScript program demonstrating a function expression assigned based on ternary condition

let myVar = true;

let funcExp = myVar ? function() { return "True"; } : function() { return "False"; }

function func1() {
  return funcExp();
}

function main() {
  let res = func1();
  console.log(res);
}

main();