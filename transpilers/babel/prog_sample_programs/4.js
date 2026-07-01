// Program to demonstrate array destructuring with default values referencing outer variables

let name = "Tom";
let age = 20;

const arr = [name];

const destructuringFunction = () => {
  const [name = "Jerry", age = 30] = arr;
  return { name, age };
};

function func1() {
  return destructuringFunction();
}

function main() {
  const res = func1();
  console.log(res);
}

main();