// Demonstrating function expressions returning destructured objects with computed keys

const objectBuilder = () => {
    let variable = 'Key';
    let object = { 
        [variable + '1']: 'Value1', 
        [variable + '2']: 'Value2' 
    };
    return object;
}

function func1(){
    let {Key1: key1, Key2: key2} = objectBuilder();
    return {key1, key2};
}

function main() {
    let res = func1();
    console.log(res);
}

main();