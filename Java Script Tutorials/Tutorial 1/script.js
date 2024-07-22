var a="hello"
console.log(typeof(a))
b=56
console.log(typeof(b))
c=true
console.log(typeof(c))
// 1a=55
// &1=55


// build in function

// var a=parseInt(prompt("enter the 1st number"))
// var b=parseInt(prompt("enter the 2nd number"))
// console.log(a+b)
// alert("how are you")

var c=document.getElementById("answer")
// compare string
var a="hello world"
var b="helo world"

if (a===b) {
    console.log(true)
}
else if(a!==b)
{
    console.log(false)
}


/*
data types
let
let

    Scope: let is block-scoped, meaning it is only available within the block (enclosed by {}) in which it is declared.
    Hoisting: Variables declared with let are also hoisted but not initialized. Accessing them before the declaration results in a ReferenceError.
    Re-declaration: You cannot re-declare the same variable within the same scope using let.
var

    Scope: var is function-scoped, meaning it is available throughout the function in which it is declared. If declared outside of a function, it's globally scoped.
    Hoisting: Variables declared with var are hoisted to the top of their scope, but only the declaration is hoisted, not the initialization.
    Re-declaration: You can re-declare the same variable within the same scope using var.
const
    Scope: const is block-scoped, similar to let.
    Hoisting: Variables declared with const are hoisted but not initialized. Accessing them before the declaration results in a ReferenceError.
    Re-declaration: You cannot re-declare the same variable within the same scope using const.
    Mutability: const variables must be initialized at the time of declaration, and their value cannot be reassigned. 
    However, if the variable holds an object or an array, the contents of the object or array can still be modified.
*/


function create() {
    var temp=document.getElementById("template")
    temp.innerHTML='</div>'+
    '<input type="number" name="number1" value="" id="number1">'+
    '<input type="number" name="number2" value="" id="number2">'+
    '<button onclick="add()">add</button>'+
    '<button onclick="sub()">sub</button>'+
    '<button onclick="mul">mul</button>'+
    '<button onclick="div()">div</button>'+
    '<button onclick="mod()">mod</button>'+
    '<button onclick="pow()">pow</button>'+
    '<button onclick="comp()">comp</button>'
    '<div>'
}
function del() {
    var temp=document.getElementById("template")
    var ans=document.getElementById("answer")
    temp.innerHTML=""
    ans.innerHTML=""
}
// commenting in js

//Normal function
function add() {
    let a=parseInt(document.getElementById("number1").value)
    let b=parseInt(document.getElementById("number2").value)
    console.log(a+b)
    // alert(a+b)
    c.innerHTML="<b>The answer for addition is </b>"+(a+b)
}

//arrow function
let sub=()=>{
    let a=parseInt(document.getElementById("number1").value)
    let b=parseInt(document.getElementById("number2").value)
    console.log(a-b)
    // alert(a-b)
    c.innerHTML="<b>The answer for subtraction is </b>"+(a-b)

}


//Anonymus function
function mul(){
    var a=parseInt(document.getElementById("number1").value)
    var b=parseInt(document.getElementById("number2").value)
    console.log(a*b)
    // alert(a*b)
    c.innerHTML="<b>The answer for multiplication  is </b>"+(a*b)

}
function div() {
    var a=parseInt(document.getElementById("number1").value)
    var b=parseInt(document.getElementById("number2").value)    
    if (b!=0) {
        console.log(a/b)
        // alert(a/b)
        c.innerHTML="<b>The answer for division is </b>"+(a/b)

    }
    else
    {
        console.log("zero can not be a denominator")
        // alert("zero can not be a denominator")
        c.innerHTML="<b>zero can not be a denominator</b>"

    }
}
function mod() {
    var a=parseInt(document.getElementById("number1").value)
    var b=parseInt(document.getElementById("number2").value)
    if (b!=0) 
    {
        console.log(a%b)
        // alert(a%b)
        c.innerHTML="<b>The answer for modulus is </b>"+(a%b)
    }
    else
    {
        console.log("zero can not be a denominator")
        // alert("zero can not be a denominator")
        c.innerHTML="<b>zero can not be a denominator</b>"

    }
}
function pow() {
    var a=parseInt(document.getElementById("number1").value)
    var b=parseInt(document.getElementById("number2").value)
    let ans=1;
   for (let i = 0; i < b; i++) {
        ans=ans*a;
   }
   //While loop
   /*
   i=0;
   while (i<b) {
    ans=ans*a;
    i++;
    
   }
    */
   //do while loop
   /*
   i=0
   do {
    i++;
    ans=ans*a;
   } while (i<b);
    */
   console.log(ans)
    // alert(ans)
    c.innerHTML="<b>The answer is </b>"+(ans)

}
function comp() {
    let a=parseInt(document.getElementById("number1").value)
    let b=parseInt(document.getElementById("number2").value)
    let ans=1;
    if (a>b) {
        
        console.log("a is greater than b")
        // alert("a is greate than b")
        c.innerHTML=a+"<b> is greate than </b>"+b
    }
    else if(a<b)
    {
        console.log("a is lesser than b")
        // alert("a is lesser than b")
        c.innerHTML=a+"<b> is less than </b>"+b

    }
    else
    {
        console.log("a is equal to b")
        // alert("a is equal to b")  
        c.innerHTML=a+"<b> is equal </b>"+b
  
    }
}


let arr=[1,2,3,4,5,6,7]
let obj={a:3,b:2,c:3}

console.log(arr.push(8))
console.log(arr.length);
console.log(arr.join(arr));
console.log(arr.slice(2,5))
console.log(arr.concat([9,10,20]))
// console.log(arr.reverse())
console.log(arr.toString())
console.log(arr[0]);
console.log(arr.unshift(0))
console.log(arr)

arr.map((e)=>{console.log(e)})