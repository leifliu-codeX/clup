import{A as a}from"./api_clusterManage.30301838.js";import{n as t}from"./index.73971a8d.js";import"./index.dfdb83b1.js";import"./vendor.194c4086.js";import"./bus.d56574c1.js";const e={};var o=t({name:"ModifyDatabaseHaStateDialog",data:()=>({dialogFormVisible:!1,loading:!1,form:{state:"",cluster_id:0,db_id:0},formRules:{},language:""}),props:{},mounted(){},methods:{openDialog(a){this.language=localStorage.getItem("language_clup"),this.form.state=a.state+"",this.form.cluster_id=a.cluster_id,this.form.db_id=a.db_id,this.dialogFormVisible=!0,console.log(this.form)},saveDatabaseHaState(){const t=this;this.$refs.modifyDatabaseHaStateForm.validate((e=>{if(!e)return;t.loading=!0;let o=Object.assign({},t.form);a.changeDatabaseHaState(o).then((a=>{t.$emit("setDatabaseHaStateFinished",this.form),t.dialogFormVisible=!1,t.loading=!1}),(function(a){t.loading=!1}))}))}}},(function(){var a=this,t=a.$createElement,e=a._self._c||t;return e("el-dialog",{attrs:{title:a.$t("ModifyDatabaseHaStateDialog.xiugai-shujukude-HA-zhuangtai"),visible:a.dialogFormVisible,"append-to-body":!0,width:"300px;"},on:{"update:visible":function(t){a.dialogFormVisible=t}}},[e("el-row",[e("el-form",{directives:[{name:"loading",rawName:"v-loading",value:a.loading,expression:"loading"}],ref:"modifyDatabaseHaStateForm",attrs:{"element-loading-text":a.$t("Public.ping-ming-jia-zai-zhong"),model:a.form,rules:a.formRules,"label-width":"en"==a.language?"240px":"170px"}},[e("el-row",[e("p",{staticStyle:{color:"red","font-size":"14px","word-break":"normal","overflow-wrap":"break-word"}},[a._v(a._s(a.$t("ModifyDatabaseHaStateDialog.zhuyi-zhiyouzai-message"))+" ")]),e("p",{staticStyle:{color:"red","font-size":"14px","word-break":"normal","overflow-wrap":"break-word"}},[a._v(" "+a._s(a.$t("ModifyDatabaseHaStateDialog.1-beikudao-zhukude-message")))]),e("p",{staticStyle:{color:"red","font-size":"14px","word-break":"normal","overflow-wrap":"break-word"}},[a._v(" "+a._s(a.$t("ModifyDatabaseHaStateDialog.2-zhuku-chuxianwenti-message")))]),e("p",{staticStyle:{color:"red","font-size":"14px","word-break":"normal","overflow-wrap":"break-word"}},[a._v(a._s(a.$t("ModifyDatabaseHaStateDialog.pingshibuyao-suibian-message")))]),e("el-col",{attrs:{span:12}},[e("el-form-item",{attrs:{label:a.$t("ModifyDatabaseHaStateDialog.qignshezhi-shujukude-HA-zhuangtai"),prop:"state"}},[e("el-select",{staticStyle:{width:"100%"},attrs:{placeholder:a.$t("createDatabasePage.qing-xuan-ze")},model:{value:a.form.state,callback:function(t){a.$set(a.form,"state",t)},expression:"form.state"}},[e("el-option",{attrs:{label:"Normal",value:"1"}}),e("el-option",{attrs:{label:"Fault",value:"2"}}),e("el-option",{attrs:{label:"Failover",value:"3"}}),e("el-option",{attrs:{label:"Switching",value:"4"}}),e("el-option",{attrs:{label:"Repairing",value:"5"}})],1)],1)],1)],1),e("div",{staticClass:"dialog-footer",staticStyle:{float:"right"}},[e("el-button",{attrs:{type:"primary"},on:{click:a.saveDatabaseHaState}},[a._v(a._s(a.$t("licManager.bao-cun")))])],1)],1)],1)],1)}),[],!1,i,"67fd20bc",null,null);function i(a){for(let t in e)this[t]=e[t]}var l=function(){return o.exports}();export{l as default};