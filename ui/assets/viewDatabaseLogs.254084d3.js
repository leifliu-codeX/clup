import{A as t}from"./api_dbManage.3ee885d4.js";import{c as e}from"./staticTools.84335405.js";import{n as i}from"./index.00f40289.js";import"./index.dfdb83b1.js";import"./vendor.194c4086.js";import"./bus.d56574c1.js";const o={};var a=i({data:()=>({dialogWidth:0,isSmallSidebar:1,fileName:"",db_id:"",log_directory:"",log_destination:"",loading:!1,viewDatabaseLogsShow:!1,fileContentIsShow:!1,paginationInfo:{currentPage:1,size:10,total:0},filePaginationInfo:{currentPage:1,size:1,total:0},row:{},logsList:[],fileLogArray:[],fileRowInfo:{}}),methods:{view(t){this.fileContentIsShow=!0,this.fileRowInfo=t,this.fileName=t.file,this.$nextTick((()=>{document.querySelector(".fileCotentClass .file-footer .el-pagination__total").innerHTML=this.$t("viewDatabaseLogs.gong-number-ye",["0"])})),this.getFileLogsInfo(this.fileRowInfo)},getFileLogsInfo(e){let i={page_num:this.filePaginationInfo.currentPage,log_directory:this.log_directory,log_destination:this.log_destination,file_name:e.file,db_id:this.db_id};t.getPgLogContent(i).then((t=>{this.filePaginationInfo.total=t.total,this.fileLogArray=t.content.split("\n"),this.$nextTick((()=>{document.querySelector(".fileCotentClass .file-footer .el-pagination__total").innerHTML=this.$t("viewDatabaseLogs.gong-number-ye",[this.filePaginationInfo.total])})),this.loading=!1}),(t=>{this.loading=!1}))},getInfo(){let i={page_size:this.paginationInfo.size,page_num:this.paginationInfo.currentPage,db_id:this.db_id};this.loading=!0,t.getPgLogFileList(i).then((t=>{this.paginationInfo.total=t.total,this.log_directory=t.log_directory,this.log_destination=t.log_destination,this.logsList=t.file_info_list.map(((t,i)=>(t.number=i+1,t.st_size=e(t.st_size),t))),this.loading=!1}),(t=>{this.loading=!1}))},openDialog(t){this.row=t,this.viewDatabaseLogsShow=!0,0==document.getElementsByClassName("showSidebar").length?(this.isSmallSidebar=1,this.dialogWidth=document.body.clientWidth-60):(this.dialogWidth=document.body.clientWidth-180,this.isSmallSidebar=2),this.db_id=t.db_id,this.getInfo()},sizeChange(t){this.paginationInfo.size=t,this.getInfo()},currentChange(t){this.paginationInfo.currentPage=t,this.getInfo()},fileCurrentChange(t){this.filePaginationInfo.currentPage=t,this.getFileLogsInfo(this.fileRowInfo)},closeFileContentDialog(){this.fileContentIsShow=!1,this.filePaginationInfo={currentPage:1,size:1,total:0},this.fileLogArray=[],this.fileRowInfo={}},updateTable(){this.viewDatabaseLogsShow=!1,this.paginationInfo={currentPage:1,size:10,total:0},this.logsList=[],this.$emit("close-form")}}},(function(){var t=this,e=t.$createElement,i=t._self._c||e;return i("div",[i("el-dialog",{ref:"queryLog",attrs:{title:t.$t("viewDatabaseLogs.chakanshujuku-rizhi")+" ( DB -"+t.row.host+":"+t.row.port+")","append-to-body":!1,"custom-class":1==t.isSmallSidebar?"querylog querylogmin":"querylog querylogmax",modal:!1,width:t.dialogWidth+"px",top:"0",visible:t.viewDatabaseLogsShow,"close-on-click-modal":!0},on:{close:t.updateTable,"update:visible":function(e){t.viewDatabaseLogsShow=e}}},[i("el-table",{directives:[{name:"loading",rawName:"v-loading",value:t.loading,expression:"loading"}],staticStyle:{width:"100%"},attrs:{data:t.logsList,border:"","element-loading-text":t.$t("Public.ping-ming-jia-zai-zhong")}},[i("el-table-column",{attrs:{prop:"number",label:t.$t("viewDatabaseLogs.xuhao"),align:"center",width:"80px"}}),i("el-table-column",{attrs:{prop:"file",label:t.$t("AgentStatusView.wenjian-ming"),align:"center","show-overflow-tooltip":""}}),i("el-table-column",{attrs:{prop:"st_ctime",label:t.$t("dashboard.chuangjian-shijian"),align:"center","show-overflow-tooltip":""}}),i("el-table-column",{attrs:{prop:"st_size",label:t.$t("viewDatabaseLogs.wenjian-daxiao"),align:"center","show-overflow-tooltip":""}}),i("el-table-column",{attrs:{label:t.$t("dbList.cao-zuo"),align:"center"},scopedSlots:t._u([{key:"default",fn:function(e){var o=e.row;return[i("el-link",{staticClass:"detail",attrs:{size:"mini"},on:{click:function(e){return t.view(o)}}},[t._v(t._s(t.$t("clusterDefine.cha-kan")))])]}}])})],1),i("div",{staticClass:"block clearfix"},[i("div",{staticClass:"fr"},[i("el-pagination",{ref:"pagination",attrs:{layout:"total, sizes, prev, pager, next, jumper","page-size":t.paginationInfo.size,"current-page":t.paginationInfo.currentPage,total:t.paginationInfo.total,"page-sizes":[10,20,30,40,50]},on:{"size-change":t.sizeChange,"current-change":t.currentChange}})],1)]),i("el-dialog",{staticClass:"fileCotentClass",attrs:{title:t.fileName,visible:t.fileContentIsShow,"append-to-body":!0,top:"5vh","close-on-click-modal":!1},on:{close:t.closeFileContentDialog}},[i("div",{staticClass:"file-body"},[t.fileContentIsShow?i("el-card",{staticClass:"file-card",attrs:{shadow:"never","body-style":"border: none !important;"}},[i("div",{staticStyle:{"overflow-y":"auto"}},t._l(t.fileLogArray,(function(e,o){return i("p",{key:o,staticStyle:{"font-size":"14px"}},[t._v(t._s(e))])})),0)]):t._e(),i("div",{staticClass:"file-footer"},[i("el-pagination",{ref:"filePagination",attrs:{layout:"total, prev, pager, next, jumper","page-size":t.filePaginationInfo.size,"current-page":t.filePaginationInfo.currentPage,total:t.filePaginationInfo.total,"page-sizes":[10,20,30,40,50]},on:{"current-change":t.fileCurrentChange}})],1)],1)])],1)],1)}),[],!1,n,"23e20606",null,null);function n(t){for(let e in o)this[e]=o[e]}var l=function(){return a.exports}();export{l as default};