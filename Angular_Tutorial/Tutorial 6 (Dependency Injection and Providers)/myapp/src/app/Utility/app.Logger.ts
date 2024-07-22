//browser console
//email
//Db
/**
 * interface Ilogger
 */
export interface Ilogger{
    log():void;
}
export class Baselogger implements Ilogger{
    log(){
        console.log("Using Console Logger");
        
    }
    
}
export class consoleLogger implements Baselogger {
    log(){
        console.log("using console Logger");
    }
}
export class Dblogger implements Baselogger {
    log(){
        console.log("using Db Logger");
        
    }
    
}
export class Filelogger implements Baselogger {
    log(){
        console.log("using File Logger");
        
    }
    
}