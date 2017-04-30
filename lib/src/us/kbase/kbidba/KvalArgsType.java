
package us.kbase.kbidba;

import java.util.HashMap;
import java.util.Map;
import javax.annotation.Generated;
import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;


/**
 * <p>Original spec-file type: kval_args_type</p>
 * <pre>
 * Input parameters for running idba_ud.
 * string workspace_name - the name of the workspace from which to take
 *    input and store output.
 * list<paired_end_lib> read_libraries - Illumina PairedEndLibrary files
 *     to assemble.
 * string output_contigset_name - the name of the output contigset
 * </pre>
 * 
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
@Generated("com.googlecode.jsonschema2pojo")
@JsonPropertyOrder({
    "mink_arg",
    "maxk_arg",
    "step_arg"
})
public class KvalArgsType {

    @JsonProperty("mink_arg")
    private Long minkArg;
    @JsonProperty("maxk_arg")
    private Long maxkArg;
    @JsonProperty("step_arg")
    private Long stepArg;
    private Map<String, Object> additionalProperties = new HashMap<String, Object>();

    @JsonProperty("mink_arg")
    public Long getMinkArg() {
        return minkArg;
    }

    @JsonProperty("mink_arg")
    public void setMinkArg(Long minkArg) {
        this.minkArg = minkArg;
    }

    public KvalArgsType withMinkArg(Long minkArg) {
        this.minkArg = minkArg;
        return this;
    }

    @JsonProperty("maxk_arg")
    public Long getMaxkArg() {
        return maxkArg;
    }

    @JsonProperty("maxk_arg")
    public void setMaxkArg(Long maxkArg) {
        this.maxkArg = maxkArg;
    }

    public KvalArgsType withMaxkArg(Long maxkArg) {
        this.maxkArg = maxkArg;
        return this;
    }

    @JsonProperty("step_arg")
    public Long getStepArg() {
        return stepArg;
    }

    @JsonProperty("step_arg")
    public void setStepArg(Long stepArg) {
        this.stepArg = stepArg;
    }

    public KvalArgsType withStepArg(Long stepArg) {
        this.stepArg = stepArg;
        return this;
    }

    @JsonAnyGetter
    public Map<String, Object> getAdditionalProperties() {
        return this.additionalProperties;
    }

    @JsonAnySetter
    public void setAdditionalProperties(String name, Object value) {
        this.additionalProperties.put(name, value);
    }

    @Override
    public String toString() {
        return ((((((((("KvalArgsType"+" [minkArg=")+ minkArg)+", maxkArg=")+ maxkArg)+", stepArg=")+ stepArg)+", additionalProperties=")+ additionalProperties)+"]");
    }

}
