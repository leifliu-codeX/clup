import{P as t}from"./index.dfdb83b1.js";import{n as e}from"./index.b91a9f18.js";import"./vendor.194c4086.js";import"./bus.d56574c1.js";var i=e=>t("/api/v1/get_general_task_log",e),l=e=>t("/api/v1/do_terminate_basebackup",e);const o={};var a=e({name:"taskLog",data:()=>({loading:!1,content:"",closing:!1,intervalID:"",showTaskDetailVisible:!1,taskId:"",curHeight:"",lastSeq:0,closeCallBack:null,reading:!1,isPauseScreen:!1,logState:1}),methods:{stopTask:function(){const t=this;this.$confirm(t.$t("taskLog.queren-tingzhi")+t.taskId+t.$t("taskLog.de-rizhi-ma"),t.$t("index.ti-shi"),{type:"warning",closeOnClickModal:!1}).then((()=>{t.loading=!0;let e={task_id:t.taskId};l(e).then((function(e){t.loading=!1,clearInterval(t.smallIntervalID)}),(function(e){t.loading=!1}))})).catch((()=>{}))},openDialog:function(t,e,i){this.content="",this.taskHtml="",this.showTaskDetailVisible=!0,this.taskId=t,this.curHeight=document.documentElement.clientHeight-250,this.lastSeq=0;let l=this;l.closeCallBack=e,l.timeoutId&&console.log("**** timer "+l.timeoutId+" not destroy!!!"),l.retriveTaskLog(i),l.timeoutId=setInterval((()=>{l.retriveTaskLog(i)}),1e3),console.log("create timeoutid="+l.timeoutId)},retriveTaskLog:function(t){let e=this,l={task_id:e.taskId,get_task_state:1,seq:e.lastSeq};e.reading=!0,i(l).then((function(t){let i=t;e.LogDatashow(i,0)}),(function(t){e.loading=!1,e.reading=!1,clearInterval(e.timeoutId)}))},LogDatashow:function(t,e){const i=this;let l="",o=t.data;i.logState=t.state,console.log(t);for(let s=0;s<o.length;s++){let t="INFO";-1==o[s].log_level?t="WARN":-2==o[s].log_level?t="ERROR":-3==o[s].log_level?t="FATAL":1==o[s].log_level&&(t="DEBUG"),l+="<p>"+o[s].create_time+"&#X3000;"+o[s].seq+"&#X3000;"+t+"&#X3000;"+o[s].log+"</p>"}i.content=l,console.log("intervalID:"+i.intervalID),l||(i.content=i.$t("taskLog.zanwu-rizhi"));let a=document.getElementById("task_info");if(i.isPauseScreen||i.$nextTick((()=>{a.scrollTop=a.scrollHeight})),0!==t.state)return clearInterval(i.timeoutId),void(i.reading=!1);0!==o.length&&(console.log(o[o.length-1].seq),o[o.length-1].seq),i.reading=!1},closeDialog:function(){this.showTaskDetailVisible=!1,clearInterval(this.timeoutId),this.closeCallBack&&(console.log("call closeCallBack"),this.closeCallBack())},handleClose:function(t){if(this.closing=!0,this.reading){console.log("==== wait closing for API.getGeneralTaskLog call return...");let e=this;setTimeout((function(){e.handleClose(t)}),100)}else this.timeoutId&&(console.log("In close Dialog clearTimeout"+this.timeoutId),clearTimeout(this.timeoutId),this.timeoutId=""),this.closing=!1,t(),this.$emit("close-refresh"),this.closeCallBack&&(console.log("call closeCallBack"),this.closeCallBack())}},destroyed(){clearInterval(this.intervalID)}},(function(){var t=this,e=t.$createElement,i=t._self._c||e;return i("div",[i("el-dialog",{directives:[{name:"loading",rawName:"v-loading",value:t.loading,expression:"loading"}],staticStyle:{"text-align":"left"},attrs:{title:t.$t("taskLog.rizhi-xinxi"),"modal-append-to-body":!1,"append-to-body":!0,visible:t.showTaskDetailVisible,"close-on-click-modal":!1,"element-loading-text":t.$t("taskLog.nuli-zhuangzaizhong"),width:"70%","before-close":t.handleClose,"lock-scroll":""},on:{"update:visible":function(e){t.showTaskDetailVisible=e}}},[i("div",[i("div",{directives:[{name:"loading",rawName:"v-loading",value:t.closing,expression:"closing"}],attrs:{"element-loading-text":t.$t("taskLog.zhengzai-guanbi-message")}},[i("div",{staticClass:"clearfix",staticStyle:{margin:"10px"}},[i("div",{staticClass:"fr"},[0===t.logState&&!1===t.isPauseScreen?i("el-button",{on:{click:function(e){t.isPauseScreen=!0}}},[t._v(t._s(t.$t("taskLog.zanting-shuaxin")))]):t._e(),0===t.logState&&!0===t.isPauseScreen?i("el-button",{attrs:{type:"primary"},on:{click:function(e){t.isPauseScreen=!1}}},[t._v(t._s(t.$t("taskLog.huifu-shuaxin")))]):t._e()],1)]),i("el-card",{staticClass:"box-card",staticStyle:{"overflow-y":"auto"},style:{height:t.curHeight+"px"},attrs:{shadow:"never",id:"task_info","body-style":"border: none !important;"}},[i("div",{domProps:{innerHTML:t._s(t.content)}})])],1)])])],1)}),[],!1,s,"3760d50c",null,null);function s(t){for(let e in o)this[e]=o[e]}var n=function(){return a.exports}();export{n as default};