// Exercising the construct: guard clause with early return inside arrow function

let x = 5;

const guardClauseExample = () => {
    if(x < 0)
        return "Negative number";
    if(x > 10)
        return "Number larger than 10";
    return x;
}

let func1 = () => {
    return guardClauseExample();
}

let main = () => {
    let res = func1();
    console.log(res);
}

main();